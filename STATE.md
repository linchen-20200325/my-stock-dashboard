# 專案戰情室 (Project State)

## 📌 當前狀態
- **專案**: 台股 AI 戰情室（Streamlit Cloud + GitHub，Python 3.x）
- **版本**: v10.62.0 | main
- **部署**: Streamlit Cloud，需設定 `FINMIND_TOKEN` + `GEMINI_API_KEY` + `PROXY_URL`
- **三大法人**: TWSE BFI82U via `fetch_url`（自動降級直連），`tables` fallback，`row[3]` 元÷1e8=億，5天回溯
- **融資餘額**: 6 段備援 — Plan 0=FinMind `TaiwanStockTotalMarginPurchaseShortSale`（v10.56.0 新增，海外 IP 唯一可達），Plan A=TWSE `rwd/MI_MARGN`，Plan B-E=HiStock/Goodinfo/Yahoo/cnyes 網爬
- **融資維持率**: ⛔ **v10.54.0 已移除**（Streamlit Cloud 非台灣 IP，三段備援頻繁失敗，治本拆除）
- **冷啟動 Lazy Load** (v10.54.0): 冷啟動只跑 3 個 thread (intl/tw/tech)；inst/margin/adl/li 改按鈕觸發，治 `Code: 1ST`
- **URL 狀態同步** (v10.54.0): `chips_loaded` ↔ `?chips=1` 雙向同步，治手機 SessionInfo 重連
- **Cache OOM 防護** (v10.54.0): 全檔 `@st.cache_data` 加 `max_entries=10`，防 1GB RAM 撐爆
- **基金淨值**: `data_loader.fetch_fund_nav(fund_id)` 接 MoneyDJ YP010001 HTML via `fetch_url` + BeautifulSoup
- **🔌 架構**: Squid Proxy（`PROXY_URL`）唯一出口；`fetch_url()` 內建 300s Storm Shield 快取，防 API 連線風暴
- **FRED**: 所有 FRED 呼叫統一加 `FRED_API_KEY`（secrets），JSON API 端點，timeout 12s
- **Streamlit 封印**: `.streamlit/config.toml` `runOnSave=false`、`logger.level=error`
- **App 初始化**: `_app_boot_done` gate 確保 `cache_data.clear()` 每 Session 僅執行一次；同步從 `query_params` 恢復狀態
- **風控**: ATR×1.5 動態停損（`risk_control.py` v4.0），`atr=None` 自動降回固定 -8%
- **MA60**: 三日確認法則（Hysteresis），防季線盤整雙巴
- **AI 輸出**: `st.write_stream()` 打字機效果；gate pattern 防重複呼叫 Gemini
- **Monte Carlo**: 10,000 路徑改為手動按鈕觸發，不自動阻塞頁面
- **L5 AI 邊界**: 禁止 Google Search Grounding；所有資料由 L1 傳入，AI 層純推理
- **v4 策略引擎簡化** (v10.54.0): `evaluate_market_status_v4_final()` 移除 `is_margin_danger`；空頭情境統一「🔴 空頭防禦（持倉 20–40%）」
- **✅ PR #141 merged**（2026-05-05）— fetch_fund_nav + fetch_margin_ratio
- **✅ PR #142 merged**（2026-05-05）— 診斷頁擴充 + FRED JSON API + VIX/NDC/Export 修復
- **✅ PR #143 merged**（2026-05-05）— Phase C：MA60 Hysteresis + ATR停損 + AI串流 + L5邊界 + 文件同步
- **✅ PR #144 merged**（2026-05-05）— Phase D：Storm Shield + Init Gate + 融資維持率 OpenAPI + DSO 🟡
- **✅ PR #145 merged**（2026-05-05）— Detox：iterrows()→vectorized + 重複 import 清理 + .ipynb 刪除
- **✅ PR #6 merged**（2026-05-06）— EDU_GUIDE 指標解讀手冊（12 個核心指標教學卡）
- **🚀 v10.54.0**（2026-05-06）— 維持率移除 + 冷啟動瘦身 + query_params 恢復 + Cache OOM 防護
- **✅ PR #15 merged**（2026-05-06）— PMI 三段救援（FRED+MacroMicro+ISM）+ 個股 Raw Data 對齊 MJ 體檢 + 診斷頁瘦身 -310 行
- **🚀 v10.55.0**（2026-05-06）— 資料診斷回歸初衷：只答「有沒有抓到 / 過不過期」；個股紅燈 1:1 對應 MJ N/A 項目
- **✅ PR #17 merged**（2026-05-06）— 融資餘額 FinMind 治本（6 段備援）+ 診斷表 4 欄元資料 + 合約負債 MOPS 備援
- **🚀 v10.56.0**（2026-05-06）— 融資餘額 FinMind 治本（海外 IP 6 段備援）；診斷表加「來源/端點/Proxy/日期」4 欄；合約負債 FinMind→MOPS 備援
- **✅ PR #19 merged**（2026-05-06）— 個股 Raw Data 對齊 MJ 五大模組 + 補 5 個底層原料 + 新增「適用 MJ 指標」欄
- **🚀 v10.57.0**（2026-05-06）— 個股 Raw Data 按 MJ 五大模組（氣長/好生意/翻桌率/還債/那根棒子）重組；補 5 個底層原料（現金/應收/EPS/預付款項/其他非流動資產）；新增「適用 MJ 指標」欄
- **✅ PR #21 merged**（2026-05-06）— MJ 計算治本：安全邊際公式 + FinMind `_build()` 防覆蓋 + AR alias 擴充 + 5y CF status
- **🚀 v10.58.0**（2026-05-06）— MJ 計算治本：(A) 安全邊際公式修正為 `oi/gp`（line 153 docs 已寫但 code 抄錯），(A') `_build()` 改 max-abs 防 FinMind 子科目覆蓋合計（治 6770 om/nm >100%），(B) AR alias 加 em-dash/破折號/全形括號變體，(D) `fetch_5_years_cash_flow` OCF=0 改回 insufficient_data 不再悶吐 0%；oi/ni 加 sanity check（>rev×1.2 視為誤抓）
- **✅ PR #23 merged**（2026-05-06）— `fetch_5_years_cash_flow` OCF=0 治本：`_sum()` match origin_name + plural CashFlowsFromOperating + fuzzy fallback
- **🚀 v10.59.0**（2026-05-06）— `fetch_5_years_cash_flow` OCF 抓取治本：`_sum()` 同時比對 `type+origin_name`（原版只比 type，中文 alias 永遠白寫）；`_OCF` alias 補對齊 data_loader 的 plural `CashFlowsFromOperatingActivities` + 帶括號中文（`營業活動之淨現金流入（流出）`）；加 OCF fuzzy fallback；治 6770 力積電「分子缺失」N/A
- **✅ PR #26 merged**（2026-05-06）— `_job_macro` as_completed timeout partial 保留 + 診斷頁三態 UX
- **🚀 v10.60.0**（2026-05-06）— `_job_macro` 治本：`as_completed(timeout=70)` 觸發 TimeoutError 時的 partial _r 保留（原本 raise 出去全部丟失，導致 `macro_info` 永不寫入 → 診斷頁 6 個 macro 全紅）；加 `_loaded_at` 時間戳 + `_all_failed` failsafe；診斷頁區分「⏸️ 尚未抓取」🟡（macro_info 不存在）vs「❌ 抓取失敗」🔴（抓過但全失敗）
- **✅ PR #28 merged**（2026-05-07）— Macro 三層重試迴圈拆除 + 內外 executor `shutdown(wait=False)`
- **🚀 v10.61.0**（2026-05-07）— Macro 治本第二刀：拆三層隱藏重試迴圈（`5 分鐘出不來`）。(1) `proxy_helper.fetch_url` 加 `attempts: int = 3` 參數，macro/m1b 全部走 `attempts=1` 砍掉外層 `range(3)` × `urllib3 Retry(total=3)` × `sleep(2.5-6.0)` 隨機等待；(2) `_fetch_export` MOF 月份迴圈從 `range(0,4)` 砍到 `range(0,2)`（當月+上月），最壞 8→4 個 URL；(3) 內外兩層 `with ThreadPoolExecutor:` 改手動 try/finally + `shutdown(wait=False)`，as_completed timeout 後立刻逃離（原本 with-exit `shutdown(wait=True)` 會卡到 stuck thread 自然結束 ~240s 拖爆外層 result(80s) → `macro_info` 永遠寫不進去）。預期：每個 fetcher 上限 ~12s，整個 macro job 最壞 ~30-40s
- **🚀 v10.61.1**（2026-05-07）— 漏網修補 + 100/100/10 UI 透明化：(1) `macro_core.py` 新增的 `fetch_tw_pmi()` 4 段 + `fetch_ism_pmi()` 3 段共 7 處 `fetch_url(...)` 全部補 `attempts=1`（PR #30/#31 別 session 加進來時忘了帶，等於繞過 v10.61.0 lean path），治台灣 PMI 🔴 未取得；(2) 個股「🛡️ 第一關」KPI 卡的 100/100/10 規則改在 A/B/C 三項分別顯示 ✅/❌/⚪，Fail 原因一目了然（門檻 A>100% / B≥100% / C>10% 與 `financial_health_engine:416/423/431` 對齊；N/A 含「5年」等假數字用先 `'N/A' in s` 短路防誤判）
- **🚀 v10.61.2**（2026-05-07）— 診斷頁 3 修：(1) 個股 raw data optional 缺失從 🟡 改 🔴（`etf_dashboard:3324` `_row` helper + `:3838` `_add_field` helper），語意改為「🟡=時效延遲、🔴=完全抓不到」；(2)「⚠️ 資料異常清單」加 `_all_section_rows` accumulator pattern，5 個 expander（總經/大盤+籌碼/先行指標/個股/ETF）的 detail rows 都會併入清單，個股 + ETF granular missing 不再隱形（schema 用 `_norm_anom()` 統一映射 `日期↔最新日期`、`狀態↔新鮮度`，按資料名稱去重）；(3) `app.py:_fetch_pmi` 失敗時改只回傳 `{'_err_pmi': ...}`，不再帶 `value:None` junk key 進 `macro_info`，異常清單會顯示具體錯誤訊息（如 `MacroMicro:NoneType | CIER:Timeout`）便於下一輪診斷
- **🚀 v10.62.0**（2026-05-07）— 來源升級 PMI + ETF 費用率：(1) `macro_core.fetch_tw_pmi()` 新增**方案 0 = 國發會 NDC** 為 primary（鏡像 `nas_server.py:218` composite endpoint pattern：4 個 URL 變體 `/PMI`、`/pmi`、`/PMI/latest`、`/indicator/PMI/latest` + 多 JSON shape parser 容錯 list/`{data:[]}`/`{items:[]}`/單筆 dict），失敗才降到既有 4 段（MacroMicro/CIER/StockFeel/鉅亨）；(2) `etf_dashboard.fetch_sitca_expense_ratio()` 新函式從**投信投顧公會 SITCA**（`sitca.org.tw IN2222_01`）抓台股 ETF 內扣費用率，用 `pandas.read_html()` defensively 找含「代號+費用率」欄位的表格 → `get_etf_expense_ratio_safe()` 改為 SITCA primary、yfinance fallback；(3) **不動 MOPS 個股**（per-stock POST body 沙箱無法驗證，等下輪 F12 截圖）。攻堅原則：multi-endpoint fallback + multi-shape parser，沙箱無法 fetch 但生產走 NAS proxy，部署後看 console log iterate

## 🏗️ 核心模組
| 檔案 | 職責 |
|------|------|
| `app.py` | Streamlit 主程式（Tab1 市場/Tab2 個股/Tab3 組合/Tab4 總經/Tab5 ETF/Tab6-9 ETF子頁） |
| `data_loader.py` | FinMind HTTP API 財報抓取（BS/CF/IS）+ yfinance 備援 |
| `financial_health_engine.py` | MJ財報體檢六大模組 + `no_ai_overall_verdict()` 老師動態結論 |
| `scoring_engine.py` | 多因子健康評分引擎（技術/籌碼/基本面/VCP） |
| `daily_checklist.py` | 國際/台股/法人籌碼/融資/先行指標抓取 |
| `market_strategy.py` | market_regime() 大盤狀態判定 |
| `macro_state_locker.py` | AI 總經裁決 + 原子鎖寫入 macro_state.json |
| `macro_alert.py` | VIX/CPI/PMI/PCR 等總經警示規則引擎 |
| `etf_dashboard.py` | ETF 診斷/組合/回測/AI 四子頁 |
| `unified_decision.py` | 統一投資決策（stock/etf/portfolio 三模式 3-Card UI） |
| `leading_indicators.py` | 外資期貨/PCR/ADL 先行指標 |
| `ai_engine.py` | Gemini AI 個股分析 |
| `risk_control.py` | 停損停利/倉位控制 |

## ✅ 最新異動（v10.54.0 — 2026-05-06）

### 維持率移除 + 冷啟動瘦身 + query_params 恢復 + Cache OOM 防護（commit `10eb287`）

**動機**：手機開頁先後遭遇兩個 Streamlit Cloud 錯誤——
- `Bad message format - Tried to use SessionInfo before it was initialized`（鎖屏回來 WebSocket 重連失敗）
- `Huh. Received no response from server. Code: 1ST`（後端 worker 沒回應）

**根因**：冷啟動 7 個 ThreadPool job × 最久 55s 阻塞，超過 websocket 心跳 30s；
1GB RAM 限額被 cache 堆爆 OOM；維持率 fetcher 每次失敗額外吃 8.3s。

**Phase 1 — 全面移除融資維持率**
- `daily_checklist.py`：刪 `fetch_margin_maintenance_ratio()` (138 行多源備援) + `get_margin_ratio()`
- `evaluate_market_status_v4_final()` 移除 `margin_maintenance_ratio` 參數與 `is_margin_danger` 分支
- `data_loader.py` / `nas_server.py`：刪 `fetch_margin_ratio()` / `_fetch_margin_ratio()`
- `data_config.py`：移除 `margin_ratio` 的 PRIORITY/TTL
- `data_registry.py`：刪 TWSE 維持率 + Wantgoo 備援兩筆 entry
- `etf_dashboard.py`：診斷頁兩處維持率 row
- `app.py`：刪 import / `_job_margin_ratio` thread / UI 警示三段 / `cl_items` 一行
- 刪除 `test_debug.py`（純維持率 big5 解析測試）

**Phase 2 — 冷啟動瘦身（治 Code: 1ST）**
- 7 個 thread 拆成 3 自動（intl/tw/tech，~30s）+ 3 lazy（inst/margin/adl，按鈕觸發）
- 先行指標 (`build_leading_fast`) 也歸入 lazy 區塊
- 新增「📊 載入籌碼面+先行指標」按鈕；`chips_loaded=True` 觸發 + 設 query_params

**Phase 3 — st.query_params 狀態恢復（治 SessionInfo）**
- `_app_boot_done` gate 內讀取 URL `?chips=1` → `chips_loaded=True`
- 全程 sync：`chips_loaded` 寫回 URL，使重整頁可恢復
- 預留 `?sid=` 個股代號通道供未來個股 Tab 啟動讀取

**Phase 4 — Cache OOM 防護**
- 全 15 個 `@st.cache_data` 加 `max_entries=10`，防 DataFrame 無限堆積撐爆 RAM

**驗證**：py_compile 全綠（7 檔），淨減 320 行（-484/+164）

---

## ✅ 歷史異動（v10.53.0 — 2026-05-05）

### Detox：iterrows() 向量化 + 重複 import 清理 + .ipynb 刪除（PR #145）

- `app.py` 5 處 `iterrows()` → Pandas vectorized（三大法人/成交量/EPS/年份dict/yoy列表）
- `app.py` 移除重複 `from concurrent.futures import ...`（2處）、刪除 dead `backtest_engine` import
- `daily_checklist.py` 移除重複 `import re as _re_mb`
- 刪除 `台股AI戰情室_*.ipynb` × 2（共 ~6,000 行）

---

### Phase D：Storm Shield + 初始化閘門 + 融資維持率 OpenAPI（PR #144）

- `proxy_helper.py`：`_URL_CACHE` dict（TTL=300s）— `fetch_url()` 相同請求直接命中快取，防 API 連線風暴
- `app.py`：`_app_boot_done` gate — `cache_data.clear()` 每 Session 僅執行一次
- `.streamlit/config.toml`：`runOnSave=false` + `[logger] level=error`
- `daily_checklist.py`：融資維持率新增 Method C：TWSE OpenAPI（`verify=False`，無 IP 限制）
- `etf_dashboard.py`：DSO 診斷 🔴→🟡（服務業無 AR 屬正常）

---

### Phase C：MA60 Hysteresis + ATR 動態停損 + AI 串流 + L5 邊界（PR #143）

- `market_strategy.py`：MA60 三日確認法則（`ma60_above_3d/below_3d`），防季線盤整雙巴
- `risk_control.py` v4.0：`atr_stop_price()` ATR×1.5；`atr=None` 自動退回 -8%
- `etf_dashboard.py`：Monte Carlo 10k 路徑改手動按鈕觸發
- `app.py`：`st.write_stream()` 打字機效果；gate pattern 防重複呼叫 Gemini
- `ai_engine.py`：移除 Google Search Grounding；新增 `analyze_stock_trend_stream()`
- `STRATEGY_MANUAL.md` v1.1 + `ARCHITECTURE.md` 全面同步

---

### NAS Proxy 全面整合 + FRED_API_KEY + 新抓取函式（v10.52.16 — PR #141/142）

**所有台灣政府網站 & FRED 呼叫已全面走 `fetch_url()`（NAS Proxy 台灣IP）：**

**`app.py`**:
- `_fetch_ndc()`: 換用 `fetch_url()` + 多策略fallback（CKAN v1 JSON / ODS CSV / 行動版HTML）
- `_fetch_export()`: MOF CSV + FRED export 均用 `fetch_url()` + `FRED_API_KEY`
- M1B / CPI / PMI FRED 呼叫：改 `fetch_url()` + `FRED_API_KEY`，timeout 降至 8s

**`daily_checklist.py`**:
- `fetch_margin_maintenance_ratio()`: 改接 TWSE MI_MARGN JSON + wantgoo HTML 備援（棄 FinMind paywall）
- `is_margin_danger` 比較前加 `float()` 強制轉型，修復 TypeError crash

**`data_loader.py`**:
- 新增 `from proxy_helper import fetch_url as _fetch_url_dl`
- TWSE T86 / TPEx / MOPS 月營收：`requests.get()` → `_fetch_url_dl()`
- 新增 `fetch_fund_nav(fund_id)`: MoneyDJ YP010001 BeautifulSoup，回傳 `{date, nav}` 或 None
- 新增 `fetch_margin_ratio()`: HiStock tb-stock BeautifulSoup，100–500 範圍防呆，回傳 float 或 None

**`STRATEGY_MANUAL.md`**: 新增完整9章策略說明書

---

### TypeError 修復 + TWSE fetch_url 重構（v10.52.15）

**v10.52.15** (`daily_checklist.py` / `proxy_helper.py`):
- `fetch_margin_maintenance_ratio()` 快取比對 `is not None` → `is not _CACHE_SENTINEL`（修復 TypeError: _CACHE_SENTINEL < 160.0）
- `proxy_helper.py` 別名方向修正：`get_proxy_config = get_proxies` → `get_proxies = get_proxy_config`（TTL 快取版本正確生效）
- `fetch_institutional()` / `fetch_margin_balance()` 改用 `fetch_url()`（Response 物件 + ProxyError 自動降級直連），移除 `fetch_with_proxy`

---

### FinMind 融資維持率 + 清除 170% 硬編碼（v10.52.14）

**v10.52.14** (`daily_checklist.py` / `app.py`):
- `fetch_margin_maintenance_ratio()` 改接 FinMind `TaiwanTotalExchangeMarginMaintenance`，`FINMIND_TOKEN` env/secrets，TTL pickle cache，回傳 float% 或 None
- `evaluate_market_status_v4_final()` 移除 `margin_maintenance_ratio or 170.0`，`is_margin_danger` 改為 `margin_maintenance_ratio is not None and < 160.0`
- `app.py:1867` 移除 `_wr_margin_ratio or 170.0`，直接傳 None 至引擎

---

### Phase2 死碼清除 + 月頻診斷假警報修復（v10.52.13）

**v10.52.13** (`app.py` / `etf_dashboard.py`):
- 刪除 DBnomics 全部路徑：M1B 路徑1b、`_dbn_px()` 函式、`_fetch_export()` 方案-1/0（-135行）
- 刪除 goodinfo 配息備援4（timeout/403）
- `_light()` 月頻門檻：`≤44/69天` → `≤90/120天`，CPI/PMI 2個月延遲正確顯示 🟢
- 診斷標籤「DBnomics」→「FRED/財政部」

---

### 5項終極修復（v10.52.12）

### 5項終極修復（v10.52.12）

**v10.52.12** (`daily_checklist.py` / `app.py`):
- `fetch_institutional()` BFI82U 加 `tables[0].data` fallback；改 `'外資及陸資' in name` 精確比對
- `fetch_margin_balance()` 換 `rwd/marginBalance` 端點，遍歷 `tables` 找 `信用交易統計`，`row[5]` 仟元÷100,000=億
- `fetch_margin_maintenance_ratio()` 直接回傳 `None`（TWSE 無全市場維持率端點）
- Export 靜態備援 `yoy` 更新：3.5 → 18.9（float，:+.1f 格式相容）
- RegistryPatch macro 日期：`last_updated:'N/A'` 改為從 `macro_info` dict 提取真實 `date` 欄位

---

### 嚴格修復TWSE資料解析邏輯（v10.52.11）

**v10.52.11** (`daily_checklist.py` / `app.py`):
- `fetch_institutional()` 改用 `fetch_with_proxy` + 固定索引 `row[3]`（買賣超，元），`lstrip('-').isdigit()` 支援負數，元÷1e8=億
- `fetch_margin_balance()` 換 `exchangeReport/MI_MARGN?date=` 端點，解析 `creditList` 中 `'融資金額(仟元)'` 列的 `row[5]`，仟元÷100,000=億元
- `_fetch_export()` 所有方案失敗改靜態備援 `{yoy: 3.5, date: '2026-03 (備援)'}`

---

### 回溯機制+靜態備援+Log清理（v10.52.10）

**v10.52.10** (`daily_checklist.py` / `app.py`):
- `fetch_institutional()` 新增 TWSE BFI82U via Squid Proxy + 5天交易日回溯（週末自動跳過），千元÷100,000=億元
- `fetch_margin_maintenance_ratio()` 單次查詢改為7天回溯迴圈，stat≠OK 自動往前找最近有效交易日
- `_fetch_ndc()` 所有方案失敗改回靜態備援 `{score:39, 綠燈, 2026-03 (備援)}`，不再標記錯誤
- 刪除啟動時誤導性 `print('🚫 TWSE 已徹底停用 | Squid Proxy 模式')`

---

### 4項精準除錯（v10.52.9）

**v10.52.9** (`daily_checklist.py` / `app.py`):
- `fetch_margin_balance()` 改用中文 Key `'融資餘額'`，千元 ÷ 100,000 = 億元（原英文 Key 全部 miss → total=0）
- `fetch_margin_maintenance_ratio()` 加 `_fields = []` 初始化，防 `UnboundLocalError`
- `_fetch_ndc()` 新增 `_ndc_hdr`（完整瀏覽器 UA + Accept + Accept-Language），方案-1 & 方案0 共用，對抗 403
- `_fetch_export()` FRED `timeout` 10 → 20 秒，防 `ReadTimeoutError`

---

### 融資餘額/維持率 改接 TWSE OpenAPI（v10.52.8）

**v10.52.8** (`daily_checklist.py` / `proxy_helper.py`):
- `proxy_helper.py` 新增 `fetch_with_proxy()` — 共用安全請求函式，自動套用 `PROXY_URL`，回傳 dict/list 或 None
- `fetch_margin_balance()` 改接 TWSE OpenAPI `/v1/exchangeReport/MI_MARGN`（透過 Squid Proxy）
- `fetch_margin_maintenance_ratio()` 改接 TWSE rwd `MI_MARGN?response=json`（透過 Squid Proxy），解析 `維持率` 欄位
- `PROXY_URL` 未設定時自動回傳 N/A（不報錯）

---

### v6.0 新增功能（v10.52.7）

**v10.52.7** (`app.py` / `ai_engine.py`):
- Sidebar 新增「🔄 強制刷新數據」按鈕：`st.cache_data.clear()` + `st.rerun()`
- AI 約束 8：Price is King — 技術面破 MA20 時，即便利多新聞仍判「利多不漲=出貨訊號」
- AI 約束 9：6770 強制對應「力積電 (PSMC)」，防名稱幻覺

---

### 總經診斷修復（v10.52.6）

**v10.52.6** (`app.py` / `etf_dashboard.py`):
- `_fetch_export()` FRED 方案加入 `observation_start/end` 動態日期參數（防 stale 資料）
- `_fetch_ndc()` 新增方案-1：`requests.get()` 直連（無 proxy），繞過 Squid proxy 嘗試台灣政府 API
- 診斷 `_light()` 月頻加黃燈層：≤44天🟢、45-69天🟡、≥70天🔴
- 診斷標籤移除 "FinMind Macro" 字樣，改為「國發會」/「財政部/DBnomics」

---

### NAS FastAPI 架構完全移除（v10.52.5）

**v10.52.5** (`daily_checklist.py`):
- 刪除 `call_nas()` / `safe_fetch()` / `_NAS_BASE` / `_NAS_KEY` / `_NAS_HEADERS`（-128 行）
- `fetch_institutional` / `fetch_margin_balance` / `fetch_margin_maintenance_ratio`：快取未命中直接回傳 N/A
- `get_export_yoy` / `get_business_indicator`：直接回傳 None
- Streamlit Secrets 可移除 `NAS_BASE_URL` 與 `NAS_API_KEY`

---

### 系統連線排毒 (Network Detox，v10.52.4）

**Phase 1** — goodinfo 殭屍爬蟲全清（-150 行），錯誤訊息更新

**Phase 2** — `proxy_helper.get_proxies()` 統一出口；FRED 動態日期參數

---

### 🚫 TWSE 永久停用 — NAS 中繼站唯一模式（v10.52.3）

**v10.52.3** (`daily_checklist.py` / `proxy_helper.py` / `nas_server.py`):
- `DISABLE_TWSE = True` 永久硬編碼，不再依賴 `_NAS_BASE` 是否設定
- `fetch_institutional`：移除 BFI82U / OpenAPI / FinMind 備援，`call_nas('institutional')` → N/A
- `fetch_margin_balance`：移除 MI_MARGN × 4日 / FinMind 備援，`call_nas('margin_balance')` → N/A
- `fetch_margin_maintenance_ratio`：270行 → 20行，移除 TWSE rwd / OpenAPI / wantgoo / histock / goodinfo / wearn / FinMind，`call_nas('margin_ratio')` → N/A
- `fetch_adl`：移除 MI_INDEX 並發50線程抓取，yfinance 唯一來源
- 刪除 `fetch_via_nas()` / `_get_twse_session()` 整個函式
- 新增 `proxy_helper.py`：NAS Squid proxy 統一入口
- `get_nas_proxy()` 改呼叫 `proxy_helper.get_proxy_config()`
- **PR #126 merged**

## ✅ 舊版異動（v10.52.1）

### 三大指標修復 + NAS proxy 路由補強

**v10.52.1** (`daily_checklist.py` / `app.py`):
- **融資維持率**：方案1/2改用 `_get_twse_session()`（curl_cffi Chrome TLS + NAS proxy）；`_twse_rwd_parse` 新增方法C值域掃描（100–500%），TWSE 欄位改名仍可命中；診斷 log 印出前8個實際欄位名
- **景氣燈號**：`_fetch_ndc()` 新增方案0（4個 NDC 新版 JSON endpoint，透過 NAS proxy 路由）
- **出口年增率**：`_fetch_export()` 新增方案-1（DBnomics v22 直連，優先 `OECD/MEI_TRD` 新版 series ID）
- **PR #124 merged**

## ✅ 舊版異動（v10.52.0）

### NAS FastAPI 優先架構 + DISABLE_TWSE 旗標 + 快取 wrapper

**v10.52.0** (`daily_checklist.py`):
- 新增 `_NAS_BASE` / `_NAS_KEY`：從 `st.secrets.NAS_BASE_URL` / `NAS_API_KEY` 或 env 讀取
- 新增 `call_nas(action, payload)` — POST `{NAS_BASE_URL}/api/fetch`；NAS 未設定時即返回 `nas_not_configured`
- 新增 `safe_fetch(data_name, nas_action, fallback_fetch, ttl)` — pickle 快取 → NAS → fallback → N/A
- `DISABLE_TWSE = bool(_NAS_BASE)` — 自動偵測：NAS FastAPI 有設定才停用 TWSE；否則保留 TWSE+代理路徑
- `fetch_institutional` / `fetch_margin_balance` / `fetch_margin_maintenance_ratio`：快取後先打 NAS，NAS 失敗才走原有 TWSE/FinMind 鏈
- 新增 `get_margin_ratio()` / `get_export_yoy()` / `get_business_indicator()`：帶 `st.cache_data(ttl=...)` 裝飾的 wrapper
- 修正系統排毒：B1（`today` NameError）、B2（`selectType=MS` 回傳空）、D1（`_TWSE_CK` dead code）、I1–I3（inline imports）
- 新增 `data_config.py`：`PRIORITY` 優先順序表 + `TTL_CONFIG` + `PKL_DIR`
- 新增 `_pkl_get` / `_pkl_put` / `_pkl_clear_all`：pickle TTL 快取基礎設施
- 強制刷新按鈕呼叫 `_pkl_clear_all()`，清除 `/tmp/stock_cache/*.pkl`
- **PR #116–#121 已 merged to main**

## ✅ 舊版異動（v10.51.9）

### 融資維持率三方案修正

**v10.51.9** (`daily_checklist.py`):
- 方案0/1 `MI_MARGN`：移除 `selectType=MS`（TWSE 無效參數，靜默回傳 `stat=OK fields=[] rows=0`）；預設不帶 selectType 即回傳全市場匯總含維持率
- 方案2 OpenAPI `MiMargin`：移除失效的中文 regex，改用欄位名關鍵字比對（`maintain`/`ratio`）+ 數值範圍 100–500 掃描；加診斷 log 顯示 sample row
- 方案5 `wearn.com`：加 `apparent_encoding` big5 修正；新增 table cell 定向解析（找「維持率」儲存格同行下一欄） + row 全文 fallback
- 移除 `test_debug.py`（臨時除錯腳本）

## ✅ 舊版異動（v10.51.8）

### NAS Proxy 全指標接入 + DGBAS 無用迴圈移除

**v10.51.8** (`app.py` / `daily_checklist.py`):
- `_fetch_ndc()` / `_fetch_export()`：改用 `_mk_s()` 繼承 NAS proxy（原本各自建立不帶 proxy 的 Session）
- `_fetch_export()`：DGBAS 整塊移除（非台灣 IP 一律回 HTML，Streamlit Cloud 無解）；方案0 改用 DBnomics FRED 鏡像 `FRED/VALEXPTWM052N`
- `_fetch_ndc()`：DGBAS 整塊移除；依賴 data.gov.tw + DBnomics
- `get_nas_proxy()`：同時讀 `NAS_PROXY_URL` 與 `PROXY_URL`（相容 Secrets 不同命名）
- data.gov.tw URL 解析：補 `resourceURL` / `resourceId` 欄位

## ✅ 舊版異動（v10.51.6）

### DGBAS URL格式修正 + Export方法順序優化

**v10.51.6** (`app.py` / `daily_checklist.py`):
- `_ndc_urls`：維度格式 `....`→`1+2+3+4+5.1.1.M`，時間格式 `2023-01`→`2023-M1`（SDMX 正確規範）；timeout 15s→8s
- `_ex_urls`：同上修正 A081201010 進出口資料集
- `_fetch_export()`：FRED 移為方案0（Streamlit Cloud 非台灣IP可存取），DGBAS 降為方案1（需台灣IP備援）
- `daily_checklist.py` 方案6：FinMind 錯誤訊息補充「需 Backer 付費方案」說明，方便問題診斷

## ✅ 舊版異動（v10.51.5）

### ETF NAV直連 + 6770 CapEx別名 + AR診斷補強

**v10.51.5** (`etf_dashboard.py` / `tw_stock_data_fetcher.py` / `data_loader.py`):
- ETF NAV：`openapi.twse.com.tw` 移除 NAS proxy 強制依賴，改為先直連後 proxy 輪試
- 6770 5年現金流：CapEx 補 IFRS 16 使用權資產合併格式 + 舊格式固定資產；DIV/INV 補命名變體
- 6770 AR=0：改印全部 BS 欄位（非前30）以利診斷；補追 IFRS 15 合約資產、貿易應收款等別名

## ✅ 舊版異動（v10.51.1–v10.51.4）

### DGBAS URL 根因修正 + 6770 sanity check + 融資維持率 FinMind

**v10.51.1** `app.py`:
- DGBAS URL 多格式輪試（text/html 偵測跳下一個）
- FRED timeout 10→20s
- `data_loader.py` 6770 liab sanity check（liab/assets < 1% → fuzzy 強制重跑）

**v10.51.2** `app.py`:
- `_ndc_urls` / `_ex_urls`：`dgbasAll` → `dgbasall`（小寫），加 `endTime=2025-12`，加維度萬用字元 `....` / `.` / `1.A.=`
- NDC 方案2、方案4 內層 `except: pass` → 改印錯誤訊息

**v10.51.3** `data_loader.py`:
- AR sanity check：`ar > 0` 但 `ar/季收入 < 0.5%` → 疑似子科目，印欄位名稱並 fuzzy 強制重跑（同 liab 子科目誤配模式）

**v10.51.4** `daily_checklist.py`:
- 融資維持率方案6：FinMind `TaiwanTotalExchangeMarginMaintenance`，預計算完成，每日 21:00 更新，完全不依賴 TWSE/NAS/JS SPA

## ✅ 舊版異動（v10.51.0）

### DGBAS SDMX API XML Fallback + 6770 診斷 + 維持率方案5

**問題根因（由部署 log 確認）：**
- `[NDC/DGBAS]` / `[Export/DGBAS]`：status=200 但 `JSONDecodeError: Expecting value: line 1 column 1 (char 0)` → SDMX 伺服器預設回傳 **XML**，`Accept: application/json` 不生效
- 力積電 6770：`debt=0.0%` 持續，需要看 BS 欄位名稱才能根治

**修復內容：**
1. `app.py` `_fetch_ndc()` + `_fetch_export()` 方案0：
   - 升級 Accept header → `application/vnd.sdmx.data+json;version=1.0.0, application/json, */*`
   - JSON 解析失敗時 **ElementTree XML fallback**：解析 SDMX-ML Generic (`ObsDimension`/`ObsValue` 子元素) 及 Structure-Specific (`TIME_PERIOD`/`OBS_VALUE` 屬性) 兩種格式
   - 加印 `content-type` header 供診斷
2. `data_loader.py` `_fuzzy_bs` liab：
   - 第一次失敗後放寬（移除「準備」排除），第二次嘗試
   - 兩次均失敗時印出所有 BS 欄位名稱供診斷
3. `daily_checklist.py` 融資維持率：
   - 新增方案5 → `stock.wearn.com` 純 HTML

## ✅ 舊版異動（v10.50.9）

### NDC 景氣燈號 + 台灣出口 YoY：接入主計總處官方 SDMX API

**根本原因：** 所有現有方案均對 Streamlit Cloud 封鎖，FinMind Macro 已廢棄。

**新增方案0（兩函數共用策略）：**
- 數據源：`nstatdb.dgbas.gov.tw`（行政院主計總處總體統計資料庫，官方公開 API）
- 格式：SDMX 2.1 JSON（`data.dataSets[0].series[skey].observations`）
- 解析：遍歷所有 series key，依值範圍自動識別目標指標

| 函數 | 功能代碼 | 識別邏輯 |
|------|---------|---------|
| `_fetch_ndc()` | A120101010 景氣指標 | 值 9–45 → 景氣對策信號綜合分數 |
| `_fetch_export()` | A081201010 進出口貿易 | 值 -50~200 → YoY%; 值 10,000~200,000 → 出口值(百萬USD，再算YoY) |

**注意（已修）：** SDMX 伺服器回傳 XML 非 JSON，v10.51.0 已加入 XML 解析。

## ✅ 舊版異動（v10.50.8）

### 融資維持率 + 個股財報三大 Bug 修復

**融資維持率 `fetch_margin_maintenance_ratio()` v7：**
- **移除** 錯誤 FinMind dataset `TaiwanTotalExchangeMarginMaintenance`（返回 HTTP 400，dataset 不存在）
- **新增 方案0**：TWSE rwd + NAS proxy（若 `NAS_PROXY_URL` 存活，透過台灣 IP 繞過 Streamlit Cloud 封鎖）
- **抽出** `_twse_rwd_parse()` 共用 helper（方案0/1 共用，避免重複）
- **新增 方案3**：wantgoo.com BeautifulSoup（`margin-statistics` + `investortool/margin`，第三方源與 TWSE 無關）
- **強化 方案4**（HiStock）：改用定向 DOM 搜尋取代全文正則，提高命中率

**個股財報 Bug 1：應收帳款/DSO + 總負債/負債比 科目查無（`data_loader.py`）：**
- `_fuzzy_bs()` 新增全形/半形空白正規化（`replace(' ','').replace('　','')`），解決「負 債 總 計」等帶空白的 IFRS 科目名稱無法匹配問題
- 新增 **Pandas regex 終極兜底**：建立 DataFrame，正規化所有空白後用 `str.contains('應收帳款|應收票據')` 及 `str.contains('負債總計|負債合計|負債總額')` 進行最後一道比對

**個股財報 Bug 2：現金流量允當比率禁止單季估算（`financial_health_engine.py`）：**
- 完全移除 `b_val = round(ocf / b_denom * 100, 1)` 單季推估（即 `1Q估` 邏輯）
- `insufficient_data`（上市未滿5年）→ 顯示 `N/A（年份不足...）`，狀態 `Fail`
- 其他錯誤 → 顯示 `N/A（5年歷史資料未取得）`，狀態 `N/A`

**個股財報 Bug 3：診斷面板連動（`app.py` + `etf_dashboard.py`）：**
- `app.py`：體檢完成後額外存 `st.session_state[f'_fin_raw_{sid2}'] = _fin_raw`
- `etf_dashboard.py` 診斷 Tab 個股區塊新增三行：
  - `DSO科目（應收帳款與票據）` — ar_days > 0 → 🟢，否則 🔴
  - `負債科目（總負債）` — liab > 0 → 🟢，否則 🔴
  - `5年歷史現金流（允當比率）` — b_item_5y.status=="ok" → 🟢，否則 🔴

## ✅ 舊版異動（v10.50.7）

### 繼續修復三大資料源（第二輪）

**新的問題觀察（由部署後 log 分析）：**
- `[維持率] ⚠️ 所有方案均失敗` — TWSE rwd 對所有日期返回空 JSON，CNYES symbol 仍錯
- `[NDC/gov6099] resource keys={...}` — 等待 debug log 確認 URL 欄位名稱
- `[Export/FRED]` — v10.50.6 部署後需等 cache 過期才見效

**修復內容：**
1. `daily_checklist.py` `fetch_margin_maintenance_ratio()` v6
   - 新增方案0: FinMind `TaiwanTotalExchangeMarginMaintenance`（有 Token 最可靠）
   - 動態偵測欄位名稱（contain 'maintain'/'ratio'/'rate'）
2. `app.py` `_fetch_ndc()`
   - 方案1 加強：印出 resource[0] 所有 key（debug），改用 `rid`/`id` 建構 URL
   - 方案3 加強：遍歷 data.gov.tw + data.nat.gov.tw，均支援 rid URL
   - 方案4 新增：NDC 行動版網頁 BeautifulSoup 解析（index.ndc.gov.tw/m/）

## ✅ 舊版異動（v10.50.6）

### 三大資料源修復：維持率/NDC/出口

**問題根因（由 Streamlit Cloud log 確認）：**
- `[維持率/TWSE-exchange] ❌ status=307` — TWSE `exchangeReport/MI_MARGN` 改為重定向，`requests` 遵循 307 後端點消失
- `[NDC/gov6099] ❌ csv_url=None` — data.gov.tw API v2 resources 只有 ODS 格式，不含 CSV key
- `[Export/gov-mof] ❌ JSONDecodeError` — data.gov.tw CKAN 缺少 Accept header 返回空 body
- `[NDC/OECD-CLI] ❌ 404 NOT FOUND` — OECD CLI 不含台灣，series `TWN.LOLITOAA.ST.M` 不存在
- `[Export/dbn] ❌ ReadTimeout` — db.nomics 在 Streamlit Cloud 環境 timeout >15s

**修復內容：**
1. `daily_checklist.py` `fetch_margin_maintenance_ratio()` v5
   - 捨棄 `exchangeReport/MI_MARGN`（307），改用 `rwd/zh/marginTrading/MI_MARGN`（已驗證可用）
   - 抽共用 `_parse_ratio()` helper，掃 title + notes + data 欄位 + 全文
   - 新增方案2：TWSE OpenAPI v1 `marginTrading/MiMargin`
   - 保留方案3 HiStock BeautifulSoup
2. `app.py` `_fetch_ndc()`
   - 方案1 修復：接受 ODS/XLS/XLSX 格式，用 `pd.read_excel(engine='odf')` 讀取
   - 方案2 改為：NDC 官網 JSON API（取代失效的 OECD CLI Taiwan）
   - 方案3 新增：data.nat.gov.tw 備用域名
   - 移除次要 OECD CLI 台灣備援（series 不存在）
3. `app.py` `_fetch_export()`
   - 方案1 改為：FRED CSV `VALEXPTWM052N`（IMF 台灣月度出口，同 M1B/CPI 模式，無需 key）
   - 方案2 保留 data.gov.tw CKAN + 加 `Accept: application/json` header

## ✅ 舊版異動（v10.50.5）

### 斬斷死亡迴圈 + FinMind TaiwanMacroEconomics 廢棄修復

| 項目 | 修復內容 |
|------|---------|
| **融資餘額死亡迴圈** | `fetch_margin_balance()` 回溯上限 15→4 天；`timeout=15→5`；新增 `json.JSONDecodeError` 獨立捕捉——連續 2 次空回應立即 break，不再嘗試 30 次 |
| **融資維持率完全重寫** | 移除 10 天日期迴圈；改 `exchangeReport/MI_MARGN`（無日期自動最新，timeout=5）+ CNYES API + HiStock 三層，無一使用日期迴圈 |
| **FinMind TaiwanMacroEconomics 廢棄** | API 返回 enum validation error，dataset 已移除 |
| **NDC 景氣對策信號** | 徹底移除 FinMind；方案1 data.gov.tw 6099 CSV；方案2 OECD CLI db.nomics 直連（CLI→NDC 分數近似映射） |
| **台灣出口 YoY** | 徹底移除 FinMind；方案1 data.gov.tw 財政部進出口 CSV；方案2 db.nomics OECD Taiwan 出口序列 |
| **所有 timeout** | 嚴格 5 秒上限，防系統卡死 |

## ✅ 最新異動（v10.50.4）

### 三項資料抓取失敗修復

| 項目 | 修復內容 |
|------|---------|
| **FINMIND_TOKEN 優先序** | `daily_checklist.py` 模組層 token 改用 `st.secrets` 優先（`os.environ` 在 Streamlit Cloud 匯入時為空）|
| **融資維持率% 取得失敗** | `fetch_margin_maintenance_ratio()` 移除 NAS Proxy 閘門；新增方案1直連 `rwd/zh/marginTrading/MI_MARGN`（同 fetch_margin_balance 已驗證路徑）；方案2 先 Proxy 再直連 |
| **NDC/出口 FinMind 失敗** | `_fetch_ndc()` + `_fetch_export()` 補上 `Authorization: Bearer` header；data.gov.tw 備援升級至 CKAN v3 action API；出口新增第三層 db.nomics OECD |

## ✅ 最新異動（v10.50.3）

### Proxy 斷線自動跳過 + ETF NAV 多路備援

| 項目 | 修復內容 |
|------|---------|
| **Proxy 存活探測** | `daily_checklist.get_nas_proxy()` + `tw_stock_data_fetcher._load_proxy_config()` 均加入 TCP 探測（timeout=2s，結果快取 60s）；代理不可達自動切換直連，不再拖垮所有連線 |
| **ETF NAV goodinfo** | `fetch_etf_nav_history` 新增 goodinfo.tw `StockDetail.asp` 為 path2（不受 TWSE IP 封鎖）；雙策略 BeautifulSoup + regex |
| **FinMind 狀態碼寬鬆** | `_jstatus == 200` 改為排除已知錯誤碼，避免 proxy 環境 status=None 被誤判 |
| **ETF NAV 瀑布重排** | 新順序：FinMind(≤14d) → goodinfo.tw → TWSE(NAS only) → MoneyDJ → yfinance → FinMind兜底 |
| **ETF NAV 快取版本** | `ver=3 → 4` 強制清除舊空白快取 |

## ✅ 最新異動（v10.50.1）

### ETF NAV 根因修復 + TWSE Swagger 動態路由 + 瀑布重排

| 項目 | 修復內容 |
|------|---------|
| **FinMind token 根因** | `etf_dashboard.py fetch_etf_nav_history()` 改用 `st.secrets` 優先讀取 `FINMIND_TOKEN`；Streamlit Cloud secrets 不自動匯出至 `os.environ`，舊寫法導致所有 ETF NAV 請求無認證 → 限速 → 空資料 |
| **新鮮度閾值放寬** | FinMind ETF NAV 閾值 7d → 14d（涵蓋連假/公告延遲） |
| **瀑布順序重排** | FinMind(≤14d) → FinMind 過舊(<30d，直接用，跳過封鎖的TWSE) → TWSE(僅NAS Proxy) → MoneyDJ → yfinance → FinMind兜底 |
| **TWSE ETF NAV NAS Proxy** | TWSE OpenAPI ETF 端點加入 `proxies=get_nas_proxy()`，與 `fetch_margin_maintenance_ratio` 一致 |
| **get_twse_route_map()** | `app.py` 新增，`@st.cache_data(ttl=24h)`，fetch swagger.json 建立 `{operationId: path}` 映射 |
| **fetch_twse_openapi_by_id()** | `app.py` 新增，`@st.cache_data(ttl=1h)`，透過 operationId 動態查找路徑並回傳 DataFrame |
| **get_etf_expense_ratio_safe()** | `etf_dashboard.py` 新增，安全讀取 yfinance 費用率，任何 key 缺失回傳 None |

## ✅ 最新異動（v10.49.3）

### NAS Proxy 中繼站支援（繞過 TWSE 雲端 IP 封鎖）

| 項目 | 修復內容 |
|------|---------|
| **get_nas_proxy() 新增** | `daily_checklist.py` 頂端新增 helper，讀取 `st.secrets['NAS_PROXY_URL']` 或 env var；返回 `{'http': url, 'https': url}` 或 `None` |
| **維持率爬蟲掛載 Proxy** | `fetch_margin_maintenance_ratio()` 加入 `proxies=get_nas_proxy()`；NAS_PROXY_URL 未設定時降級為直連（不影響現有行為） |
| **Secrets 設定說明** | Streamlit Cloud Settings → Secrets 加入 `NAS_PROXY_URL = "http://IP:PORT"`；有帳密寫 `http://帳號:密碼@IP:PORT` |

## ✅ 最新異動（v10.49.2）

### 暴力精簡：三函數全部壓縮至最底層 bare requests

| 項目 | 修復內容 |
|------|---------|
| **維持率函數 70→20 行** | `daily_checklist.py fetch_margin_maintenance_ratio()` 移除 HiStock BeautifulSoup 備援方案與 `_valid()` helper；單一路徑：bare `requests.get()` + regex `整體市場維持率.*?(\d+\.\d+)` |
| **NDC 函數 35→15 行** | `app.py _fetch_ndc()` 移除 pandas DataFrame + to_numeric + sort；改為 URL 字串內嵌 query params + `data[-1]['value']` 直讀 |
| **Export 函數 35→15 行** | `app.py _fetch_export()` 移除 params dict + column 重整；改為 `df.iloc[-1]/iloc[-13]` 直算 YoY |
| **回傳格式相容** | 兩函數回傳格式維持 `{ndc_signal:{score,signal,date}}` / `{tw_export:{yoy,date,source}}`，上游 session_state 無需修改 |

## ✅ 最新異動（v10.49）

### 全面棄用 FinMind Python 套件 + 改為 bare requests.get()

| 項目 | 修復內容 |
|------|---------|
| **融資維持率 UA 升級** | `daily_checklist.py fetch_margin_maintenance_ratio()` Chrome/122 → Chrome/124 |
| **NDC 棄用 _mk_s()** | `app.py _fetch_ndc()` 改為 bare `requests.get()`；`msg=='success'`；`start_date='2023-01-01'`；`timeout=8` |
| **Export 棄用 _mk_s() + iloc[-13]** | `app.py _fetch_export()` 改為 bare `requests.get()`；`msg=='success'`；`start_date='2022-01-01'`；`timeout=8`；YoY 改用 `iloc[-1]/iloc[-13]-1` |
| **回傳格式相容** | 兩函數回傳格式維持 `{ndc_signal:{score,signal,date}}` / `{tw_export:{yoy,date,source}}` |

## ✅ 最新異動（v10.48.1）

### 融資維持率爬蟲強制重寫 + NDC/Export 總經函數精簡

| 項目 | 修復內容 |
|------|---------|
| **融資維持率強制重寫** | `daily_checklist.py fetch_margin_maintenance_ratio()` 全部替換：方案1 TWSE `MI_MARGN?response=json` + regex `整體市場維持率.*?(\d{3,4})` 取值；方案2 HiStock BeautifulSoup 備援；移除原 openapi+_TWSE_CK 依賴與 7天日期回溯迴圈 |
| **NDC 死亡迴圈消滅** | `app.py _fetch_ndc()` 移除 data.gov.tw 三層嵌套迴圈（package_search + 3 resource_ids × 2 API）；改為單次 FinMind `TaiwanMacroEconomics data_id=景氣對策信號(分)` 精準查詢；從 7379 字元削至 2450 字元 |
| **Export 函數精簡** | `app.py _fetch_export()` 移除 TaiwanExportImportTotal / TaiwanExportByIndustry 備援迴圈；改為單次 `data_id=出口-總值` 直取；最壞情況從 60s 降至 20s |
| **回傳格式相容** | 兩函數回傳格式維持 `{ndc_signal:{score,signal,date}}` / `{tw_export:{yoy,date,source}}`，上游 session_state 無需修改 |
| **Bug 修正** | 原始指令 URL Markdown 格式錯誤、函數名稱 fetch_margin_ratio → fetch_margin_maintenance_ratio、DataLoader 回傳格式不相容等 3 項 bug 均已修正 |

## ✅ 最新異動（v10.48）

### DSO N/A 根因修復 + 新聞整合至 MJ 財報體檢 AI Insight

| 項目 | 修復內容 |
|------|---------|
| **DSO N/A 根因修復** | `data_loader.py` 在 `_fuzzy_bs` 之後新增第五層兜底：從 FinMind 原始列資料（`_bs_rows`）建立 DataFrame，對 `type`/`origin_name` 欄位執行 `str.contains('應收帳款', na=False)`，排除利息/所得稅等雜項後取 `max()`；修正力積電 (6770) 等非標準科目命名導致所有精確+模糊比對失敗的情況 |
| **MJ 近期新聞整合** | `financial_health_engine.py` `_PROMPT_TEMPLATE` 新增 `<近期新聞>` 輸入區塊；`ai_insight` 輸出要求加入「請結合近期新聞，分析市場情緒與未來潛在的催化劑」 |
| **analyze_financial_health 擴充** | 新增 `news_context: str = ""` 參數；有 `api_key + news_context` 時呼叫 Gemini 生成含新聞情緒的 `ai_insight`/`red_flags`；失敗靜默降級保留純計算結果 |
| **app.py 新聞抓取** | 財報體檢前先呼叫 `_fetch_stock_news(sid2, name2, 3)` 抓取 3 則個股新聞，格式化後傳入 `analyze_financial_health()`；Tab3 批次比較路徑（`api_key=""`）不受影響 |

## ✅ 最新異動（v10.47 hotfix）

### altair/Python3.14 TypeError + Streamlit 版本鎖定

| 項目 | 修復內容 |
|------|---------|
| **st.bar_chart altair crash** | `app.py:3893` `st.bar_chart(_bc_df)` → `plotly.graph_objects.Bar` 直繪；Python 3.14 + altair 5.x 環境下 `altair.vegalite` 已移除，st.bar_chart 內部呼叫觸發 TypeError |
| **altair 版本鎖定** | `requirements.txt` 新增 `altair>=4.0.0,<5.0.0`，防止 5.x 再次引入相容性問題 |
| **Streamlit 版本鎖定** | `requirements.txt` `streamlit>=1.32.0` → `>=1.36.0,<1.41.0`；避免 1.41+ 對 `unsafe_allow_html=True` 的 breaking change |

## ✅ 最新異動（v10.45 hotfix）

### Streamlit HTML 顯示異常修復

| 項目 | 修復內容 |
|------|---------|
| **HTML 渲染為純文字** | `.streamlit/config.toml` 新增 `enableMarkdownUnsafeHTML = true`；Streamlit Cloud 1.40+ 將 `unsafe_allow_html=True` 改為需顯式啟用，否則全頁 HTML/CSS 標籤均顯示為純文字 |

## ✅ 最新異動（v10.44）

### FinMind start_date=2015 + histock 維持率爬蟲 + analyze_20d_chips

| 項目 | 修復內容 |
|------|---------|
| **FinMind Macro rows=0** | `app.py` NDC 景氣 + Export `_fm_get7` 兩處 `start_date` 由 `2020-01-01` 改為 `2015-01-01`；FinMind 需足夠歷史資料否則常回傳空值 |
| **維持率爬蟲替換** | `daily_checklist.py` 方案2 以 `histock.tw/stock/margin.aspx` BeautifulSoup 取代廢棄的 cnyes；優先 regex `維持率後接數字`，備援掃描 130~400 浮點數 |
| **analyze_20d_chips** | 新增個股近 20 日籌碼集中度分析函數（`daily_checklist.py`）：指標A 集中度 = (外資+投信)淨買總張數 / 總成交張數 × 100%；指標B 延續性 = 買超天數佔比；單位統一為「張」無需換算 |
| **個股Tab §G** | `app.py` 個股分析新增「近 20 日籌碼集中度」UI：`st.metric` 顯示集中度+延續性，`st.progress` 視覺化比例，訊號列 🔥大戶吸籌 / 🔴大戶倒貨 / 🟡籌碼發散 |

## ✅ 最新異動（v10.43）

### cnyes 死亡端點清除 + 三大法人柱狀圖改 st.bar_chart

| 項目 | 修復內容 |
|------|---------|
| **cnyes 軟404清除** | `daily_checklist.py fetch_margin_maintenance_ratio()` 方案2 cnyes 整塊移除（HTTP 200 但回傳「頁面不存在」HTML，爬蟲無用）；改為直接 print 端點失效提示後 return None |
| **三大法人柱狀圖空白** | `app.py:3884` 改用 `st.bar_chart()`（Plotly 在 Streamlit Cloud 渲染異常）；DataFrame 以 `外資/投信/自營商` 三欄建立，index 為日期字串，呼叫前 `.astype(float)` 確保型別正確 |

## ✅ 最新異動（v10.42）

### FRED BOM 修復 + cnyes Next.js + DeprecationWarning 清除 + 法人圖表接入

| 項目 | 修復內容 |
|------|---------|
| **FRED `Missing column 'DATE'`** | 改用 `parse_dates=[0]` 位置索引 + BOM strip，根治 FRED CSV 欄名含 `﻿` 前綴的解析失敗；CPI/PMI timeout 12s→15s |
| **cnyes Next.js SPA** | 升級為 `__NEXT_DATA__` JSON 提取（SSR初始狀態）+ 全文 regex + 標籤特徵數字 + debug HTML 印出；移除 `www.twse.com.tw` 方案3/4（永遠 JSONDecodeError） |
| **utcfromtimestamp** | `app.py:2634` 改為 `fromtimestamp(t, timezone.utc)`，消除 Python 3.14 DeprecationWarning |
| **use_container_width** | `st.plotly_chart` 兩處改為 `width='stretch'`（只替換 chart element，保留 dataframe/button 原有參數） |
| **三大法人空白圖表** | `bar_chart_institutional` 補 `_all_zero` 佔位 bar + 提示 annotation；在 app.py 三大法人 section 接入 `st.plotly_chart(bar_chart_institutional(...))` |

## ✅ 最新異動（v10.41）

### 死亡迴圈斬斷 + FRED parse_dates 根因修復 + FinMind status=None 防禦

| 項目 | 修復內容 |
|------|---------|
| **TWSE 死亡迴圈** | `fetch_margin_maintenance_ratio` 方案3/4 從 5/3 天縮為 **2 天**（max_retries=2）；方案3加 `_m3_json_fails` 計數器，連續 JSONDecodeError ≥2 次立即 `break`，阻斷 TWSE 封鎖觸發的無限重試 |
| **FRED Missing column** | `_fetch_cpi()` / `_fetch_pmi()` 移除 `index_col='DATE'`（與 `parse_dates=['DATE']` 同用在 pandas 2.x 引發 ValueError）；改為 `parse_dates=['DATE']` + `reset_index(drop=True)`；下游存取改用 `_df['DATE'].iloc[-1]` 與 `[c for c in cols if c != 'DATE'][0]` |
| **FinMind status=None** | `_fm_get7()` 改為「排除已知錯誤碼 (≥400)，data 存在即接受」邏輯；修復 FinMind 在 proxy 環境下回傳無 status key 導致整個 export 放棄的問題 |
| **效能改善** | 最壞情況阻塞從 120s (5天×2×12s) 降至 ~4s（2次 JSONDecodeError < 1s 即判定封鎖並中斷） |

## ✅ 最新異動（v10.40）

### Python 3.14 相容性 + TWSE 爬蟲防護 + DX-Y.NYB 修復

| 項目 | 修復內容 |
|------|---------|
| **Python 3.14 SyntaxWarning** | `app.py` 蔡森/春哥 ASCII art `st.markdown("""` → `st.markdown(r"""` 消除 `\ ` invalid escape |
| **DX=F → DX-Y.NYB** | `daily_checklist.py` INTL_MAP 美元指數 DXY 主 symbol 改為 `DX-Y.NYB`；`_sym_list` 順序改為 `['DX-Y.NYB', 'DX=F', 'UUP']` |
| **TWSE Chrome UA** | `daily_checklist.py:692` MI_INDEX 抓取 `headers=HDR`（Chrome/120 完整 UA）；`daily_checklist.py:339` MI_MARGN openapi `headers={**HDR,'Accept':'application/json'}` |
| **TWSE Chrome UA (app.py)** | `app.py:275` TWT49U 除權息 + `app.py:4497` MI_INDEX 上漲下跌家數 → 全升級為完整 Chrome UA，防 TWSE JSONDecodeError |
| **連線測試 UA** | `app.py:1189` sidebar 連線測試 TWSE 探測也升級為 Chrome/120 UA |

## ✅ 最新異動（v10.39，commit `ed4ea55`，PR #79）

### FinMind 欄位大小寫正規化 + 出口精確 indicator

| 項目 | 修復內容 |
|------|---------|
| **欄位正規化** | `_fetch_ndc()` / `_fetch_export()` 加入 `df.columns = [c.lower()]`；防 FinMind 回傳 `Indicator`（大寫）時整個 if 判斷靜默跳過 |
| **出口精確比對** | `indicator == '出口-總值'` 取代 `str.contains('出口')`；備援改為 groupby 取最多行的單一 indicator |
| **YoY 計算** | `.pct_change(12) * 100` 取代手算 `iloc[-1]/iloc[-13]` |
| **start_date 固定** | 兩函數均改為 `'2020-01-01'`，確保有足夠 12 個月計算同比 |
| **debug print** | 印出 FinMind 回傳的 indicator 清單，方便後續排查 |

## ✅ 最新異動（v10.38，commit `d891f88`）

### pandas_datareader 移除 + FRED CSV 直連 + 頻率欄位

| 項目 | 修復內容 |
|------|---------|
| **requirements.txt** | 移除 `pandas-datareader`（與 pandas 3.0+ 不相容，import 即 TypeError） |
| **CPI 抓取** | `_fetch_cpi()` 改用 `requests.get(fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCSL)` 純 CSV，無需 API Key |
| **PMI 抓取** | `_fetch_pmi()` 同上，NAPM→MANEMP→INDPRO 三級降級鏈 |
| **診斷 UI 頻率欄** | `render_data_health_raw._row()` 新增「頻率」欄：日頻/月頻/季頻/不定期 |
| **final_check.py** | CHECK1 改用 FRED CSV pure requests |

## ✅ 最新異動（v10.37，commits `f21cf6e` + `2ef5b0b`）

### 融資維持率修復 + API錯誤透明化 + final_check.py

| 項目 | 修復內容 |
|------|---------|
| **融資維持率 UI fallback** | `app.py:1912` 由「顯示融資餘額億數」改為「未取得 (N/A)」，防止數值誤導 |
| **fetch_margin_maintenance_ratio 重寫** | 4-method 瀑布：openapi.twse → cnyes BeautifulSoup → www MI_MARGN JSON（7日回溯）→ TWT93U；每方案明確 print 錯誤類型 |
| **API 錯誤透明化** | `_fetch_vix/cpi/pmi/ndc/export` 失敗時返回 `{'_err_xxx': 'FRED:ConnectTimeout | BLS:HTTPError'}` 存入 `macro_info`；診斷 UI `_row()` 顯示錯誤原因（而非只顯示「未取得」） |
| **_light() 閾值對齊** | `render_data_health_raw._light()` 更新：daily=5d, monthly=60d, quarterly=150d, yearly=always🟢（與 `_freshness()` 一致） |
| **final_check.py（新）** | 三項健診：CHECK1 CPI日期（FRED→BLS），CHECK2 2330季報日期，CHECK3 2330合約負債值（str.contains） |

## ✅ 最新異動（v10.36，commit `640c869`，PR #76）

### 新鮮度容忍升級 + UI來源名稱全面更新 + 殘餘dbnomics清理

| 項目 | 修復內容 |
|------|---------|
| **_freshness() yearly** | 有資料即 🟢（股利 848天前正確顯示，消除誤判🔴） |
| **_freshness() quarterly** | 90天→**150**天為 🟢（覆蓋 Q3→Q4 四個月財報空窗；117天前 = 🟢） |
| **_freshness() monthly** | 45天→**60**天為 🟢（覆蓋次月底延遲公佈） |
| **_freshness() daily** | 3天→**5**天為 🟢（覆蓋連假） |
| **UI 來源名稱清理** | `render_data_health_raw()` / macro info table / KPI卡片 / LLM context 全面移除 dbnomics / IMF / OECD CLI / data.gov.tw / TaiwanExportImport 字眼，統一顯示 FRED / FinMind Macro |
| **_fetch_pmi 殘餘dbnomics** | 方案2 dbnomics OECD PMI block 完整刪除（PR#74 漏刪） |
| **_fetch_export 殘餘dbnomics** | 方案3 dbnomics OECD/IMF block 完整刪除 |
| **test_fetch.py** | 新增 FRED CPI + FinMind NDC 快速驗證腳本 |

## ✅ 最新異動（v10.35，commit `75194a3`，PR #74）

### 破解快取陷阱 + NDC精確比對 + 合約負債DataFrame提取（app.py + data_loader.py + daily_checklist.py）

| 項目 | 修復內容 |
|------|---------|
| **快取強制清除** | `app.py` session 首次執行 `st.cache_data.clear()`（`_cache_cleared_v10_35` 旗標防重複）；`fetch_quarterly` `_ver` 3→4；`fetch_quarterly_extra` 新增 `_ver=2` |
| **TTL 統一** | `fetch_quarterly` ttl 1800→3600 |
| **NDC 精確比對** | `_fetch_ndc` 改用 `indicator=='景氣對策信號(分)'` 精確比對，備援 `str.contains('景氣對策信號')`；新增 debug 印出 FinMind 所有 indicator 清單 |
| **CPI 清理** | 移除 dbnomics IMF 備援路徑（保留 FRED 主路徑 + BLS 次路徑） |
| **PMI 清理** | 移除 dbnomics OECD PMI + CLI 所有備援路徑（FRED 唯一路徑） |
| **融資維持率** | `daily_checklist` 新增方案 3：TWSE MI_MARGN CSV + regex 提取 |
| **合約負債 DataFrame 提取** | `get_quarterly_bs_cf` 先建 `_bs_df_raw`（sort 降冪）；以 `type.str.contains('合約負債')` 加總（涵蓋 ASCII/全形/em dash 所有變體）；失敗才降級 `_val()` + dict fuzzy |
| **test_fetchers.py** | 新增離線單元測試（Part A 全通過：A1 date欄位 / A2 CL提取 / A3 NDC比對）+ 線上整合測試（Part B，供 Streamlit Cloud 環境） |

## ✅ 最新異動（v10.34，commit `54a7132`，PR #73）

### 修復失效的總經/籌碼/個股財報 API 管線（app.py + data_loader.py + daily_checklist.py）

| 項目 | 修復內容 |
|------|---------|
| **CPI** | 新增 pandas_datareader FRED `CPIAUCSL` 主路徑（proxy env 注入）；BLS/dbnomics 降為備援 |
| **PMI** | 新增 FRED `NAPM`→`MANEMP`→`INDPRO` 主路徑；dbnomics OECD 降為備援 |
| **NDC 景氣燈號** | 新增 FinMind TaiwanMacroEconomics 主路徑；data.gov.tw 降為備援 |
| **台灣出口 YoY** | 新增 FinMind TaiwanMacroEconomics 主路徑；TaiwanExportImportTotal/dbnomics 降為備援 |
| **融資維持率** | MI_MARGN 新增搜尋 totalData+notes；加 TWSE TWT93U 備援端點 |
| **季報 date 欄位** | qtr/qtr_extra 加 end-of-quarter date 欄（2025Q4→2025-12-31）供診斷正確讀取 |
| **合約負債模糊加總** | _CL_KEYS 擴充含-流動/-非流動；精確 match 失敗時 contains 加總所有子科目 |
| **requirements.txt** | 新增 `pandas-datareader>=0.10.0` |

## ✅ 最新異動（v10.33，commit `7dee262`，PR #72）

### 資料診斷 macro_info key 修正（etf_dashboard.py）

| 項目 | 說明 |
|------|------|
| **CPI key 修正** | `'cpi'` → `'us_core_cpi'`（BLS/dbnomics 實際回傳 key） |
| **PMI key 修正** | `'pmi'` → `'ism_pmi'`（OECD CLI 實際 key） |
| **NDC key 修正** | `'ndc'` → `'ndc_signal'`（NDC/OECD CLI 代理實際 key） |
| **M1B date 修正** | `m1b_m2_info` 無 `date` 欄位，改以 `cl_ts` 作為時間代理 |
| **margin_ratio 判斷修正** | 數值 `0` 會被 `if val` 誤判缺失，改為 `is not None` |

## ✅ 最新異動（v10.32，commit `a5e3eca`，PR #71）

### Phase 2 UI 重構：平坦 8-Tab + 資料診斷 Raw-only + 教學 Markdown（app.py + etf_dashboard.py）

| 項目 | 說明 |
|------|------|
| **平坦 8-Tab 結構** | `總經 / 產業熱力圖 / 個股 / 個股組合 / ETF / ETF組合 / 資料診斷 / 教學`，移除舊的巢狀 Tab 包裝層 |
| **ETF組合子 Tab** | 內建 3 子頁：`組合配置 / 歷史回測 / ETF AI`（`_tab_etf_port/_tab_etf_bt/_tab_etf_ai`） |
| **資料診斷 Raw-only** | 新 `render_data_health_raw()` 函式：5 個 expander（總經/大盤籌碼/先行指標/個股/ETF），每列 3 欄（資料名稱/最後更新/狀態燈號），嚴格排除所有計算值（RSI/MA/KD 等） |
| **教學 Markdown** | 靜態 `st.expander` 4 師：孫慶龍（合約負債/資本支出/EPS框架）、蔡森（破底翻/頭肩底）、春哥 VCP（4大條件/ASCII圖）、宏爺（M1B-M2/四象限矩陣） |
| **舊內容清理** | 移除 ~550 行舊巢狀 Tab 結構與 placeholder 手冊重複內容（9336→8793 行） |
| **舊變數替換** | `tab_etf1~4/tab_health/tab4_masters` → `tab_etf/_tab_etf_port/_tab_etf_bt/_tab_etf_ai/tab_diag/tab_edu` |

## ✅ 最新異動（v10.31，commits `0f34d0a`–`5da3870`）

### 全面 Proxy 修復 + 資料新鮮度改善（app.py / daily_checklist.py / data_loader.py / leading_indicators.py）

| 問題 | 根本原因 | 修正 |
|------|---------|------|
| **yfinance `proxy=` TypeError** | 新版 yfinance 不接受 `proxy=` 關鍵字參數 | 改用 `os.environ` 注入 `HTTPS_PROXY`/`HTTP_PROXY`，try/finally 還原 |
| **TWSE SSLCertVerificationError** | `build_proxy_session()` 回傳 `verify=True`；Missing Subject Key Identifier | 所有 `_bps()`/`_bps_dl()` 建立 session 後強制 `s.verify = False` |
| **FRED CPI 超時浪費 30s** | Streamlit Cloud 封鎖 FRED，每次 15s×2=30s 白費 | 完整移除 FRED CPI 直連；dbnomics IMF 備援已可正常運作 |
| **大盤指標 40→1 項** | `fetch_single()` 裸呼叫 yfinance 無 proxy；DataRegistry 在抓取失敗時不重建大盤項目 | `fetch_single()` 加 `os.environ` 注入；Registry Patch 補建大盤區塊 |
| **NDC 景氣 878天** | `dbnomics.fetch_series()` 不走 proxy；Series ID 格式錯誤 | 改用 `_dbn_px()`；ID 修正為 `OECD/MEI_CLI/TWN.LOLITOAA.ST.M` |
| **出口 391天** | OECD 資料有 12 個月延遲 | 新增 FinMind `TaiwanExportImportTotal`/`TaiwanExportByIndustry` 為優先來源（1 個月延遲） |
| **個股資料完全失敗** | `data_loader.py` 中多處裸 `yf.download()`/`requests.get()` 無 proxy | 新增 `_yf_dl()` helper（env 注入）；所有 `requests.get()` 改為 `_bps_dl().get()` |
| **SyntaxWarning `\>`** | `app.py:8476` raw string 中使用 `\>` | 修正為 `>` |
| **ADL timeout** | timeout 30s 不夠 | 調升至 55s；錯誤訊息更新 |

**關鍵程式碼模式：**
```python
# yfinance proxy 注入（相容新舊版本）
_ek = ('HTTPS_PROXY', 'HTTP_PROXY', 'https_proxy', 'http_proxy')
_bak = {k: os.environ.get(k) for k in _ek}
if _px_url:
    for k in _ek: os.environ[k] = _px_url
try:
    return yf.download(symbol, **kwargs)  # 或 yf.Ticker().history()
finally:
    for k, v in _bak.items():
        if v is None: os.environ.pop(k, None)
        else: os.environ[k] = v

# requests session（verify=False 強制）
def _bps():
    try:
        from tw_stock_data_fetcher import build_proxy_session as _b
        s = _b()
    except Exception:
        s = requests.Session()
    s.verify = False  # ← 必須，TWSE SSL 問題
    return s
```

## ✅ 最新異動（v10.30，commit `3d8bf30`）

### 總經 Macro Job 超時根因修復（app.py）— 移除確認永遠失敗的 API

| 問題 | 根本原因 | 修正 |
|------|---------|------|
| **Export 永遠 422** | FinMind `TaiwanExportStatistics` 資料集不存在，每次浪費 15s | 完整移除此區塊；OECD dbnomics 升格為主要 Export 來源 |
| **GOV 探測 ProxyError** | `api.mof.gov.tw` 在 Streamlit Cloud 透過 Proxy 連線失敗（500），且從未成功設定 `tw_export`，浪費 10s | 整個 GOV debug 區塊移除 |
| **Macro Job 超時 >80s** | FRED 15s×3 + FinMind 15s + MOF 10s 疊加 → 超過限制 → `_macro_res=None` | 合計省下 ~25s；配合 PR #61 的 FRED 5s/NDC CKAN v3，總耗時降至 ~35-45s |

**PR #61（已 merge 2026-04-26）收錄：**
- FRED PMI timeout: 15s → 5s；新增 freshness 檢查（>60天跳過舊 FRED series）
- NDC: CKAN v3 端點優先（`/api/3/action/datastore_search`）；sort key 補 `period`/`期間`
- BLS CPI: 過濾 `value='&#39;`（未公布月份）
- `build_proxy_session()` 套用至 macro + financials 請求
- `PROXY_URL` 單一 key 支援（Streamlit Cloud 格式）

## ✅ 最新異動（v10.29，commit `a3548cb`）

### 總經資料過期根因修復（app.py）
| 問題 | 根本原因 | 修正 |
|------|---------|------|
| **PMI 877天** | FRED `MFPMI01USM657S` 授權於 2023-10 終止，fetch 成功但資料是舊的，所有備援永遠無法觸發 | 加入 freshness 檢查（>60天自動跳過）；新增 `BSCICP03USM665S`、`PMDILK03USM665S` 備援系列；讓 dbnomics OECD PMI 備援得以生效 |
| **NDC 877天** | data.gov.tw resource_id 已過期 | 加入動態搜尋 API（`package_search`）預先取得最新 resource_id；sort key 補上 `period`/`期間` 欄位 |
| **Export 390天** | FinMind 422 + MOF ProxyError，從未成功取得資料 | v10.30 正式移除（詳上） |
| **Timeout** | 40s 不夠（含 Proxy 延遲） | 調升至 80s |

## ✅ 最新異動（v10.28，commit `4c76307`）

### 資料診斷全動態化：無限制類別擴充（app.py + etf_dashboard.py + test_registry.py）
| 項目 | 說明 |
|------|------|
| **欄位重命名** | `app.py` registry：`freq` → `frequency`、`latest_date` → `last_updated`（`_reg_add` / `_reg_missing` 及全部 10+ 呼叫點同步更新） |
| **動態 Tab 生成** | `etf_dashboard.py §0`：移除硬寫的 `st.tabs(['大盤','個股','ETF'])`；改為掃描 registry 中實際存在的 `category` 值動態生成；新增任意類別不需改 UI 代碼 |
| **`_disp_name()`** | 統一 registry key → 顯示名稱轉換（去 `[先行指標]` / `[ETF]` / `[個股]` 前綴，`| ` 後取細項名） |
| **`_freshness()` 參數** | 參數從 `freq` 改為 `frequency`，與 registry 欄位名一致 |
| **`_build_table()` 欄位** | 讀 `frequency`（非 `freq`）、`last_updated`（非 `latest_date`） |
| **`_CAT_ICON` 可擴充** | 替換 `_CAT_LBL` 固定字典，未登錄類別自動顯示 `📁 {cat}` |
| **全域 Banner 修復** | 摘要計算同步使用 `last_updated` / `frequency` 欄位 |
| **`test_registry.py`（新增）** | 12 個 mock 案例（日/月/季 × 最新/略舊/過期/缺失 + 跨月/跨年邊界），全部通過 ✅ |

## ✅ 最新異動（v10.27）

### 資料診斷重構：純時間戳 + 三維嚴格分類（app.py + etf_dashboard.py）
| 項目 | 說明 |
|------|------|
| **`category` + `freq` 欄位** | `_reg_add(name, df, category, freq)` — 每筆資料在登錄時即標記類別（大盤/個股/ETF）與更新頻率（daily/monthly/quarterly） |
| **移除 df 儲存** | registry 不再儲存 DataFrame 本體，僅保留 `latest_date` / `rows` / `category` / `freq`，節省記憶體且移除 df.head() 顯示 |
| **純 freq 判定新鮮度** | `_freshness(date_str, freq)` 依 freq 欄位套用門檻，不再用名稱猜測；日≤3天🟢、月≤45天🟢、季≤90天🟢 |
| **5 欄標準表** | `資料項目 / 所屬類別 / 更新頻率 / 最新資料時間 / 狀態（🟢最新/🟡略舊/🔴過期/⚫缺失）` |
| **嚴格過濾** | 依 `category` 欄位分流，大盤/個股/ETF 三 Tab 互不干擾（驗證：三域交叉過濾均為 False） |
| **移除快照 df.head()** | 刪除實體數值顯示，診斷頁僅呈現時間戳元資料 |

## ✅ 最新異動（v10.26）

### 資料診斷重構：三域分組 + Tab 切換（etf_dashboard.py）
| 項目 | 說明 |
|------|------|
| **三域 Tab** | `st.tabs(['📊 總經 & 市場', '🔬 個股', '🏦 ETF'])` |
| **總經子分組** | 🇹🇼 台股市場 / 🌐 國際指數 / 💰 固定收益 / 📈 先行指標（5細項） |
| **個股 Tab** | 強制顯示 5 細項，缺失標 ⚫；顯示股號名稱作為標題 |
| **ETF Tab** | 只在完成 ETF 診斷後出現資料 |
| **_render_group()** | 共用渲染 helper，自動計算缺/舊數量並顯示 badge |
| **全域 Banner** | 跨三域統計 ⚫缺失 / ⚠️過期總數 |
| **快照摺疊** | 改為 `st.expander` 預設收合，減少頁面長度 |

## ✅ 最新異動（v10.25）

### 個股缺失資料明確標示（app.py + etf_dashboard.py）
| 項目 | 說明 |
|------|------|
| **強制顯示 5 細項** | `t2_data` 的 df/rev/qtr/cl/cx 全部登錄；有資料正常顯示，無資料標 `missing=True` |
| **⚫ 缺失欄** | `etf_dashboard` 表格：`missing=True` → 燈號 `⚫`、新鮮度「缺失（API未回傳）」，讓合約負債/現金流量缺失一眼可見 |
| **快照過濾** | 資料抽查快照的選項排除 missing 項目，避免選到空 DataFrame |
| **Banner 分類** | 缺失數與過期數分開統計顯示（⚫ N筆缺失 / ⚠️ N筆過期） |

## ✅ 最新異動（v10.24）

### 先行指標拆細項（app.py）
| 細項 | 來源欄位 | 資料來源 |
|------|---------|---------|
| `[先行指標] 三大法人現貨` | 外資、投信、自營 | FinMind TaiwanStockTotalInstitutionalInvestors |
| `[先行指標] 外資期貨留倉` | 外資大小 | FinMind TaiwanFuturesInstitutionalInvestors |
| `[先行指標] 選擇權PCR` | 選PCR、外(選) | FinMind TaiwanOptionInstitutionalInvestors |
| `[先行指標] 成交量（TWSE）` | 成交量 | TWSE MI_INDEX |
| `[先行指標] 未平倉/韭菜指數` | 前五大留倉、前十大留倉、未平倉口數、韭菜指數 | TAIFEX（免費版多為 null） |
- 各細項排除「整列均為 null / '-'」的日期，最新日期反映該來源最後有效資料

## ✅ 最新異動（v10.23）

### Data Registry 頻率感知新鮮度（etf_dashboard.py）
| 項目 | 說明 |
|------|------|
| **_freshness(date_str, name)** | 新增 `name` 參數，依資料名稱關鍵字自動判斷更新頻率並套用對應門檻 |
| **日更新（預設）** | 🟢 0-3天（含週末）、🟡 4-5天、🔴 >5天；0=今天、1=昨天 顯示文字 |
| **月更新（月營收）** | 🟢 ≤45天、🟡 ≤75天、🔴 >75天 |
| **季更新（季財報/現金流量/資產負債）** | 🟢 ≤90天（最新一季）、🟡 ≤180天（落後一季）、🔴 >180天 |
| **新欄位「更新頻率」** | 健康總表新增欄位，顯示 📈日/📅月/📊季 |
| **警告訊息更新** | Banner 同步說明各頻率的過期標準 |

## ✅ 最新異動（v10.22）

### Data Registry 修復 + 個股/ETF 細項掃描（app.py + etf_dashboard.py）
| 項目 | 說明 |
|------|------|
| **先行指標 NaT 修復** | `_reg_add()` 優先搜尋 `_date` 欄（YYYYMMDD 格式），以 `format='%Y%m%d'` 解析；舊的 `日期` 欄（`4月23日`，無年份）不再導致 NaT |
| **NaN 安全判斷** | `_ls` 賦值加入 `pd.isna()` 防呆，避免 `NaT` 被格式化成錯誤字串 |
| **個股細項自動登錄** | 掃描 `t2_data` 的 `df/rev/qtr/cl/cx`，以 `[個股] {sid} {name} \| {類型}` 格式寫入 registry |
| **ETF 細項自動登錄** | `etf_single_data` 新增 `price_df` 欄位；registry 掃描後以 `[ETF] {ticker} {name} \| 價格走勢` 登錄 |

## ✅ 最新異動（v10.21）

### 全域資料診斷中心（app.py + etf_dashboard.py）
| 項目 | 說明 |
|------|------|
| **Data Registry** | `app.py` 在 `st.rerun()` 前呼叫 `_reg_add()`，掃描 `cl_data.intl/tw/tech`、ADL、先行指標，寫入 `st.session_state['data_registry']` |
| **自動降冪排序** | `_reg_add()` 對 DatetimeIndex 型 DF 呼叫 `sort_index(ascending=False)`；date 欄型呼叫 `sort_values(dcol, ascending=False)` |
| **無綁定標的** | Registry 完全動態，不寫死任何股票代號 |
| **全域健康總表** | `etf_dashboard.render_data_health()` 最前加入「📋 全域資料健康總表」：讀 `data_registry`，顯示名稱/最新日期/新鮮度(🟢≤5天/🟡≤14天/🔴過舊)/筆數/欄數 |
| **快照檢視器** | `st.selectbox` 選項由 registry 動態生成；選中後顯示該 DF `.head(5)` |
| **過舊偵測** | 超過 14 天顯示 ⚠️，並在底部顯示警告 banner |

## ✅ 最新異動（v10.20）

### 6770 DSO + 負債比 N/A 修復（data_loader.py）
| 項目 | 說明 |
|------|------|
| **AR L1 vsum 新增** | 括號格式：`應收帳款（非關係人）`、`（關係人）`、`淨額`後綴、`應收票據（非關係人）/（關係人）`、短橫線格式（涵蓋 IFRS 關係人拆分揭露） |
| **AR L2 vsum 新增** | `應收帳款（含稅）`、`應收帳款淨額（含稅）`（部分公司含稅列示） |
| **AR L3 v 新增** | `應收帳款（非關係人）`、`應收帳款（關係人）` 加入備援路徑 |
| **ar_p 前期 AR 擴充** | 由 3 個 alias 擴充至 9 個，補齊括號格式與含稅格式 |
| **fuzzy 排除修正** | `["稅"]` → `["所得稅", "退稅"]`：舊排除會誤殺 `應收帳款（含稅）` 等欄位 |
| **liab 新增** | `Liabilities`（英文 type）、`負債合計（千元）`、`負債總額（千元）` |
| **驗證** | `test_6770_fields.py` 三情境（括號格式/含稅/fuzzy 修復）全部通過 |

## ✅ 最新異動（v10.19，commit `3d2049a`）

### MA120 誤判根因修復（app.py + market_strategy.py）
| 項目 | 說明 |
|------|------|
| **根本原因** | `app.py:1987` 的 `fetch_single('^TWII', period='90d')` 只回傳 ~64 交易日，不足 MA120 所需 120 筆；舊程式碼用 `current_price` 填補導致 `index_close == ma120` 判定跌破 |
| **資料長度修正** | `_job_tw()` 改為 `period='9mo'`（≈195 交易日），確保 `rolling(120)` 有效運算 |
| **新鮮度守門** | `get_market_assessment` 加入 7 天有效期檢查：末筆資料超過 7 天 → `return None` + 警告 log，防止陳舊資料產生誤判 |

## ✅ 最新異動（v10.18，commit `93d811f`）

### MA120 趨勢濾網全面升級（market_strategy.py）
| 項目 | 說明 |
|------|------|
| **歷史長度修正** | `period='300d'` → `'9mo'`（≈195 交易日），確保 `rolling(120)` 有足夠有效 bars |
| **NaN 防呆** | MA120 為 NaN 時直接 `return None`，不再以 `current_price` 填補（消除「index_close == ma120」誤判跌破）|
| **三日確認法則** | 向量化比對最近 3 日收盤 vs MA120：`ma120_above_3d` / `ma120_below_3d` |
| **均線斜率** | 今日 MA120 vs 5 日前 MA120：`ma120_rising` / `ma120_falling` |
| **狀態機重構** | 🟢 晴天 = above_3d + rising；🔴 雨天 = below_3d + falling；🟡 多雲 = 所有過渡狀態（取代原分數門檻）|
| **Label 更新** | `'🟢 多頭'` → `'🟢 多頭（晴天）'`；`'🟡 中性'` → `'🟡 震盪（多雲）'`；`'🔴 空頭'` → `'🔴 空頭防禦（雨天）'` |

## ✅ 最新異動（v10.17）

### MJ 體檢表 uncaught exception 修復（app.py）
| 項目 | 說明 |
|------|------|
| **問題根因** | `fetch_financial_statements` / `analyze_financial_health` 沒有外層 try/except；若任一函式拋出例外，session state 永遠不被寫入，expander 內容崩潰且每次 rerun 重試再崩潰 |
| **修復** | `app.py:6478` 在 `st.spinner` 內加外層 `try/except Exception as _fh_exc`；捕獲後寫入 `{'error': True, 'ai_insight': f'財報體檢發生例外：{_fh_exc}'}` |
| **效果** | 即使 FinMind API 或 AI 引擎拋例外，MJ 體檢表 expander 仍會顯示（改為紅色錯誤訊息而非空白崩潰） |

## ✅ 最新異動（v10.16，branch `f688401`）

### AI 語氣升級：股海老船長 v2（commit `f688401`）
| 項目 | 說明 |
|------|------|
| **角色升級** | 台灣資深投資顧問 → 股海老船長（多次牛熊歷練、一針見血） |
| **新增守則** | 拒絕券商官腔（禁用震盪整理/逢低承接）、籌碼翻譯蒟蒻、總經翻譯對照 |
| **輸出格式** | 核心洞察 50 字以內、兄弟帶入感、條列直擊要害 |

## ✅ 最新異動（v10.15，branch `c6011fc`）

### 全站 AI 白話文語氣注入（commit `c6011fc`）
| 項目 | 說明 |
|------|------|
| **新增 `persona.py`** | 統一定義 `TAIWAN_ADVISOR_PERSONA` 常數（台灣資深投資顧問語氣） |
| **注入方式** | Gemini REST API `systemInstruction` 欄位（等效 SDK `system_instruction=`） |
| **涵蓋範圍** | `financial_health_engine._gemini_call`、`app.gemini_call`、`macro_state_locker._default_gemini_call`、`ai_engine`（3 處 payload） |
| **安全機制** | 規格第 6 條：JSON 結構欄位不受風格影響，模組 JSON 輸出格式不變 |

## ✅ 最新異動（v10.14，branch `96f4ebb`）

### OCF 單位爆炸 + 翻桌率年化 + 條件A保命符（commit `96f4ebb`）
| 項目 | 修復內容 |
|------|---------|
| **OCF 單位** | 移除 >1e6 百萬中間層（台積電千元欄位 ~3e8 誤觸）→ 兩段式：>1e9 元÷1e8；否則千元÷1e5 |
| **資產翻桌率年化** | `financial_health_engine._no_ai_operating`：分子改為 `rev×4` |
| **條件A保命符** | Tab2/Tab3 均新增 `_is_cash_exception`；現金充足時流動比率門檻放寬至 >100%；顯示 💰 Banner |

## ✅ 最新異動（v10.13，main `23b76a2`）

### 財報計算年化 + OCF 單位 + AR 別名修復（commit `23b76a2`）
| 項目 | 修復內容 |
|------|---------|
| **ROE 年化** | `_no_ai_profitability` + `_no_ai_advanced_diagnostic`：`(NI × 4) / equity` |
| **DIO 年化** | `_no_ai_operating`：分母 `cogs × 4`，天數統一 360 |
| **DSO/DPO 年化** | `data_loader`：分母 `rev/cogs × 4`，365天→360天 |
| **OCF 單位防呆** | 三段式自動偵測：>1e9 → 元（÷1e8）；>1e6 → 百萬（÷100）；其他 → 千元（÷1e5） |
| **AR 別名** | L2 _vsum 補入 `應收帳款及票據`、`應收帳款及票據淨額` |

### 新增 fetch_goodinfo_metrics()（commit `44cd2af`）
| 項目 | 說明 |
|------|------|
| **模組** | `tw_stock_data_fetcher.py` §12.6 |
| **URL** | `BS_M_QUAR`（資產總額/負債總額/應收帳款及票據）+ `IS_M_QUAR`（營業收入） |
| **格式** | `@st.cache_data(ttl=3天)`；proxies 參數相容 Streamlit Secrets |
| **計算** | `debt_ratio = 負債/資產×100`；`DSO = 360/(rev×4/ar)` |

## ✅ 最新異動（v10.11，main `d546216`）

### 財報 N/A 與 OPM 護城河誤渲染修復（3 commits `ef7a9bf` → `d546216`）
| commit | 項目 | 內容 |
|--------|------|------|
| `ef7a9bf` | **短期償債能力保命符邏輯脫鉤** | Banner 改讀 `Final_Solvency_Verdict` 字串精確比對「條件B：天天收現」；流動比率保命符啟動時閾值 300%→150%，顏色/標籤連動 |
| `9810cd4` | **ARCHITECTURE.md v6.5 + STATE.md** | 更新版本日期；STATE.md 補記 v10.8 |
| `d546216` | **AR/負債 N/A + OPM 護城河誤觸** | AR 兩段式加總（L1拆開+L2合計行）；補全 FIELD_ALIASES（資產總額/負債總額）；OPM 雙重驗證（CCC 必須是實質負數） |

### 財報判定 3 大 UI Bug 修復（commit `d4cc9ee`）
| Bug | 修復 |
|-----|------|
| ROE 負值誤判真實獲利 | 解析數值，`ROE<=0` → ❌ 本業虧損 |
| OPM N/A 誤觸護城河 | 移除 `_p_days>_r_days` 旁路 |
| N/A 誤標「特許行業」 | 按 Value 字串區分 🏦/⚪ |

## ✅ 最新異動（v10.8，main `d4cc9ee`）

### `app.py` UI 層 3 個狀態判定 Bug 修復（commit `d4cc9ee`）
| Bug | 位置 | 修復內容 |
|-----|------|---------|
| **ROE 負值誤判真實獲利** | Tab2/Tab3 ROE 卡片 | 新增數值解析，`ROE <= 0` → `❌ 本業虧損`（紅燈） |
| **OPM 護城河被 DSO=0 誤觸** | Tab2 OPM 商業話語權 | 移除 `_p_days > _r_days` 旁路；`_r_days==0` → info 缺漏提示 |
| **N/A 誤標「特許行業」** | Tab2/Tab3 負債比率卡片 | `else "特許行業"` → 按 Value 字串區分「🏦 特許行業 / ⚪ 資料缺漏」 |

### `ARCHITECTURE.md` 技術規格書完成（v6.5）
| 章節 | 說明 |
|------|------|
| §1 目錄結構 | 專案根目錄樹、各層職責、程式碼規模（1.4） |
| §2 分層架構 | L0–L5 六層設計、跨層依賴矩陣、環境變數 |
| §3 資料流向 | Session State 架構、個股/ETF/市場三大流程、資料新鮮度 |
| §4 核心函式 I/O | 8 模組 30+ 函式輸入/輸出/副作用表格（L1–L5 + app.py） |

## ✅ 最新異動（v10.7，main `769f945`）

### `financial_health_engine.py` N/A 連鎖誤判修復（commit `769f945`）
| Bug | 位置 | 修復內容 |
|-----|------|---------|
| **OPM 護城河誤判** | `_derive_basic_from_fin_data` + `_no_ai_operating` | DSO=0(N/A) 時：`advantage=False`、雷達得 -999（最低）、`OPM_Strategy="N/A (DSO缺失)"` |
| **負債比 0% 亮綠燈** | `_derive_basic_from_fin_data` | `debt_pct` 改用 `None` 預設；缺漏 → `⚪` 灰燈；雷達「財務結構」同給 -999 |
| **OCF 單位錯誤** | `_derive_basic_from_fin_data` | `÷1e6` → `÷1e5`，顯示由 `XB` 改為 `X億` |

## ✅ 最新異動（v10.6，main `6e197ef`）

### `financial_health_engine.py` 3 大邏輯 Bug 修復（commit `6e197ef`）
| Bug | 位置 | 修復內容 |
|-----|------|---------|
| **Bug 1：ROE 負值顯示綠色** | `_no_ai_advanced_diagnostic` dupont 判斷 | 新增 `roe <= 0` 分支 → `"⚠️ ROE 為負，本業虧損"` |
| **Bug 2：天天收現防呆漏洞** | `_no_ai_solvency` 條件B | `ar_days < 15` → `0 < ar_days <= 15`，DSO 為 N/A (0) 時不觸發 |
| **Bug 3：盈餘含金量公式錯誤** | `_no_ai_advanced_diagnostic` 盈餘含金量 | NI≤0 → `"N/A (本業虧損，不適用此指標)"`；NI>0 → 標準 OCF/NI |

## ✅ 最新異動（v10.5，main `5f98874`）

### 移除執行期暫存檔（commit `5f98874`）
| 項目 | 說明 |
|------|------|
| **`macro_state.json`** | `git rm --cached` 移出追蹤；`.gitignore` 補上規則，往後不再進 repo |
| **原因** | 該檔由 `macro_state_locker.py` 執行時寫入，屬執行期狀態，非原始碼 |

## ✅ 最新異動（v10.4，main `213f57a`）

### `data_loader.py` NameError 修復
| 項目 | 說明 |
|------|------|
| **錯誤** | `fetch_financial_statements` line 1755 回傳 `is_finance` 但函式內從未定義 |
| **根因** | `_is_financial_stock()` 是 `StockDataLoader` 的巢狀函式，外部不可呼叫 |
| **修法** | 改用 `stock_id.startswith(('28','58'))` 保底邏輯，與原函式 fallback 一致 |

## ✅ 最新異動（v10.3，main）

### `leading_indicators.py` Bug 修復 + 測試（commits `30ea5da` → `7dee8f9`）
| 項目 | 說明 |
|------|------|
| **Bug 1 修復** | `build_dataset` 韭菜指數：`taifex_mtx_data()` 回傳 tuple，改用 `_mtx[0] if isinstance(_mtx, tuple) else _mtx` 解包 |
| **Bug 2 修復** | `render_leading_table` PCR 顏色閾值：`0.8/1.2`（小數比率）→ `80/120`（整數百分比） |
| **新增測試** | `tests/test_leading_indicators.py`：47 個測試，8 個 class，全通過 |
| **測試涵蓋** | `roc_to_ymd` / `ymd formatters` / `to_num` / `first_num` / `months_in_range` / `extract_date` / `find_data_table` / `expand_table_elem` + Bug 2 regression（PCR 邊界值 80/120） |

### Sidebar 連線狀態面板修正（commit `7438fe0`）
| 項目 | 說明 |
|------|------|
| **FinMind 端點** | `/api/v4/info`（404）→ `/api/v4/data?dataset=TaiwanStockInfo&stock_id=2330` |
| **TWSE 端點** | `twse.com.tw/rwd`（SSLError）→ `openapi.twse.com.tw/v1/opendata/t187ap03_L` |

### 總測試數
| 模組 | 測試數 |
|------|------|
| `scoring_engine.py` | 168+ |
| `macro_state_locker.py` | 18+ |
| `macro_alert.py` | 10+ |
| `financial_health_engine.py` | 17 |
| `risk_control.py` | 既有 |
| `leading_indicators.py` | **47（新增）** |
| **合計** | **≥ 473** |

## ✅ 最新異動（v10.2，main `5c94cd4`）

### Sidebar 連線狀態面板（commit `968f2bb`）
| 項目 | 說明 |
|------|------|
| **靜態徽章** | FinMind/Gemini/Proxy 三欄，根據 Secrets 是否設定顯示 ✅/❌/— |
| **Proxy 提示** | `PROXY_HOST` 有值時顯示 `🔒 host:port` |
| **測試連線按鈕** | 點擊對 FinMind / TWSE / Yahoo Finance 發送 HTTP 探測，結果存入 `session_state['_sb_conn_results']` |
| **位置** | `app.py:1125`，Defense Mode 狀態下方，警語上方 |

## ✅ 最新異動（v10.1，branch `claude/analyze-test-coverage-070Kf`）

### 財報健檢三項 N/A 修復（commits `341b1fb`）
| 項目 | 修復內容 |
|------|---------|
| **B項現金流量允當比率** | 硬編 N/A → 單季估算 `OCF/(CapEx+ΔInv+Div)×100%`，標注「1Q估」 |
| **負債比率金融特許行業** | `is_finance=True` 時跳過60/70%門檻，顯示「金融特許行業」 |
| **DSO/AR 別名擴充** | 新增 `合約資產`、`工程應收款`、`應收票據及應收帳款` 等建設業科目 |
| **data_loader 回傳欄位** | `fetch_fin_data` 加入 `is_finance` 欄位供下游模組使用 |

### 新增模組（commit `792a7e5`）
| 檔案 | 說明 |
|------|------|
| `tw_stock_data_fetcher.py` | Proxy-aware 台股財報抓取模組（Goodinfo/MOPS 備援，501行）；`fetch_tw_financials()` 公開 API，與 `data_loader.fetch_fin_data()` 格式相容 |

### PR 批次覆蓋率分析結果
| 檔案 | 變動行數 | 測試缺口 | 處置 |
|------|---------|---------|------|
| `financial_health_engine.py` | 51 | B項3路徑、is_finance 6路徑、debt fallback 6路徑 | ✅ 新增 17 tests |
| `scoring_engine.py` | 11 | 無（existing test 已覆蓋新 early-return）| ✅ 已驗證 |
| `data_loader.py` | 9 | 無（alias 擴充 + is_finance key，整合測試範疇）| ✅ 已驗證 |

### 測試覆蓋率最終結果（commit `92cbb2b` → `84a6027`）

| 模組 | 原始 | 最終 | 新增測試 |
|------|------|------|---------|
| `scoring_engine.py` | 50% | **96%** | +168 |
| `macro_state_locker.py` | 78% | **100%** | +18 |
| `macro_alert.py` | 67% | **90%** | +10 |
| `financial_health_engine.py` | 0% | **PR分支覆蓋** | +17 |
| `risk_control.py` | 95% | 95% | — |
| **整體** | **60%** | **96%+** | **+213** |

總測試數：295 → **426**（全部通過）

#### `scoring_engine.py` 新增測試類別
- `TestCalcQualityScore` — 7 情境（None/GM↑Rev↑優質/GM↓Rev↓弱/GM→Rev↑穩健）
- `TestCalcForwardMomentumScore` — FGMS 函式（None/三率維度/is_finance=True）
- `TestCalcLeadingIndicatorsDetail` + `Extended` — I1–I5 全路徑（🟢/🟡/🔴/⚪）
- `TestCalcForwardMomentumScoreExtended` — 合約負債 + 存貨維度深路徑
- `TestBollingerSqueezeBreak` — 橫盤後跳漲觸發 `is_squeeze_break=True`
- `TestVcpAtrFilterException` / `TestCalcAtrStopException` — 字串欄位觸發 `except` 路徑

#### Bug Fix
- `calc_chip_score()`: 明確傳入 `foreign_buy` 應優先於 DataFrame 欄位（修復 1 個失敗測試）

#### `macro_state_locker.py` 新增測試類別（78% → 100%）
- `TestDefaultGeminiCall` — 7 情境：無 API Key / 200 成功 / 404 / SAFETY / 429+sleep / Exception / 空 candidates
- `TestLockSystemStateOnly` — 直寫路徑（曝險上下限 clamp、summary 格式）
- `TestCalculateSystemStateBias240` — BIAS240 雙重共振（高乖離+VIX/PMI）、低乖離加分、非數值 `_f()` 防禦
- `test_negative_m1b_m2_spread_labels_tightening` — 「資金緊縮」標籤路徑

#### `macro_alert.py` 新增（67% → 71%）
- `TestFetchMacroSnapshotEdgeCases` — VIX/CPI/PCR 非數值 → TypeError/ValueError 靜默略過

## ✅ 最新修復（v10.0，main commits `8d2320b` → `e22f613`）
| commit | 項目 | 內容 |
|--------|------|------|
| `8d2320b` | **體檢表老師動態結論 + 資產計算修復** | `no_ai_overall_verdict()` 六模組彙整生成等級A+~F；`assets = cur_assets + non_cur_assets` 兜底 |
| `6620276` | **IFRS reverse + 模糊比對 + 盈餘含金量** | reverse IFRS 移到主邏輯層；`_fuzzy_bs()` 掃全欄位；NI<0 改顯 OCF/Rev |
| `6592db8` | **引擎層重算負債比率 + Goodinfo AR 備援** | `_no_ai_financial_structure` 直接從 `流動負債(千)` 等重算；Goodinfo 季度 BS 補 AR |
| `e22f613` | **STATE.md v10.0** | 記錄財報健檢四層備援策略 |

## 📐 財報健檢資料補齊策略（四層）
```
L1: FinMind 精確欄位別名（30+ 中英文變體）
L2: FinMind 組合推算（流動+非流動相加 / IFRS 雙向恆等式）
L3: 模糊比對（掃 BS 所有欄位取最大值）
L4: yfinance + Goodinfo 外部備援
L5: 引擎層重算（直接從 fin_data 已有欄位推導）← 最終防線
```

## 🔒 已知限制
- TWSE IP 封鎖 → 全部走 FinMind/openapi 備援
- FinMind 免費帳號：每小時 600 次請求限制
- NDC 景氣燈號：主站封鎖 → OECD CLI 代理
- 收現速度(DSO)：特定產業（建設/REITs/金融業）AR 欄位名稱特殊，Goodinfo 備援中
- `macro_alert.py` lines 338-421：Streamlit 渲染函式（`render_alerts()`），需 mock `st.*`，屬整合測試範疇，未納入單元測試

## 🔑 環境變數（Streamlit Secrets）
- `FINMIND_TOKEN`: FinMind API
- `GEMINI_API_KEY`: Gemini AI（全站共用）
