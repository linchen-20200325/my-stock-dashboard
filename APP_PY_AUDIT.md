# app.py 拆檔 Audit(v18.397 P5-B3,1542 LOC)

## 規模

| 度量 | 值 |
|---|---|
| 總 LOC | 1542 |
| Top-level def | 28 |
| Top-level class | 1 (`_AppProxy`) |
| Tab orchestration block(`with tab_*`)| 6 |

## 結構分區

| 區段 | LOC | 性質 | 拆檔可行性 |
|---|---|---|---|
| L1-100 imports + bootstrap | 100 | st.set_page_config + sidebar + 全域 import | ❌ 真不可抽(app.py 入口) |
| L100-200 `_get_fm_token / _gemini_keys / gemini_call` | 100 | L3 service-level helpers | 🟡 可抽至 src/services/(部分已抽出) |
| L250-300 `_cache_key / _load_cache / _save_cache` | 50 | L0 cache layer pattern | 🟢 應抽 shared/(類似 shared/cache_layer.py 模式) |
| L284-700 `fetch_price/dividend/financials/revenue/quarterly` | 400 | L1 Data fetcher cluster | 🟢 應全部抽至 src/data/(已部分 EX-PASSTHRU-1 例外) |
| L701-800 `generate_ai_comment` | 100 | L3 AI service | 🟡 可抽至 src/services/ai_*.py |
| L803-1060 `render_health_score / _render_compass_card` | 250 | L4 Render | 🟢 應抽至 src/ui/render/ |
| L1088-1210 `render_macro_compass` | 120 | L4/L5 mixed | 🟢 應抽至 src/ui/tabs/ |
| L1210-1330 `_fetch_macro_news / _rss_items_from_bytes / _fetch_stock_news` | 120 | L1 Data fetcher(news) | 🟢 應抽至 src/data/news/ |
| L1425-1456 `_build_llm_context` | 30 | L3 AI helper | 🟡 可抽至 src/services/ |
| L1456-1542 6 個 `with tab_*` block | 90 | L6 App tab routing(orchestrator entry) | ❌ 真不可抽(app.py 本質) |

## 拆檔可行區估算

| 類別 | 估計 LOC | 規模 | 優先級 |
|---|---|---|---|
| L1 Data fetcher cluster | 400 | 大 | 高(EX-PASSTHRU-1 升 L3) |
| L4 Render | 370 | 中大 | 高(類比 tab_macro 經驗) |
| L1 News fetcher | 120 | 中 | 中 |
| L3 AI service | 130 | 中 | 中 |
| L0 Cache layer | 50 | 小 | 低(獨立 PR) |

**可抽合計**:~1070 LOC(占 1542 的 70%)。

## 拆檔藍圖(類比 tab_macro 5387→488 經驗)

### Phase B3-α(LOW risk,單一 PR)
抽 50 LOC cache helper 至 `shared/app_cache.py`(類比 `shared/cache_layer.py`)。
不破壞 API:`_cache_key/_load_cache/_save_cache` 留 thin shim。

### Phase B3-β(MED,2 PR)
- 抽 ~130 LOC AI service 至 `src/services/app_ai_service.py`
- 抽 ~120 LOC news fetcher 至 `src/data/news/`(新子目錄)

### Phase B3-γ(MED-HIGH,3-4 PR)
抽 ~370 LOC Render 至 `src/ui/render/app_render.py` + `health_score.py` + `compass.py`(3 個獨立 module)。

### Phase B3-δ(HIGH,5-7 PR)
抽 ~400 LOC L1 fetcher 至 `src/data/stock/` 子目錄(price / dividend / financials / revenue / quarterly 各 1 module)。
注意:這些已 EX-PASSTHRU-1 從 app.py import,抽完將 EX-PASSTHRU-1 部分退役。

### 預估收益
- app.py:1542 → ~470 LOC(-70%,類比 tab_macro -91% 略遜,因 app.py orchestrator 比例較高)
- 殘餘 ~470 LOC:imports + bootstrap + 6 個 tab orchestration block + service call(orchestrator)

## §-1 對齊

| 觸發條件 | 滿足? |
|---|---|
| user 實際在用 app.py | ✅(streamlit app 入口) |
| 真實 bug 觸發拆檔需求 | ❌(現況 work) |
| user 主動指派 | ✅(本 audit 是 user 要求) |
| ROI 高 | ✅(類比 tab_macro 成功經驗) |

**判定**:✅ **正式列為 TODO 隊列**,user 認可後分 11-15 個 PR 執行(類比 tab_macro 5387→488 用了 ~15 個 PR)。

## Phase 排期建議

| Phase | 規模 | 建議何時 |
|---|---|---|
| B3-α cache helper | 1 PR,~50 LOC | 任何時候(LOW risk) |
| B3-β AI + news | 2 PR,~250 LOC | 接續 α |
| B3-γ Render | 3-4 PR,~370 LOC | 接續 β,需 user 確認 UI 不破壞 |
| B3-δ L1 fetcher | 5-7 PR,~400 LOC | 最後,規模最大風險最高 |

**警示**:類比 tab_macro 經驗,執行期間會反覆「真不可抽 → 重 audit → 認錯補抽」3-4 輪。Phase 標題只是初估,不是承諾。

## 結論

app.py 拆檔是真可行 + 真有價值的 TODO。但**規模 ~1070 LOC 跨 11-15 PR**,單回合做不完。

**建議**:user 認可後逐 phase 啟動(每 phase 結束 review + commit + STATE 存檔 + 評估下 phase)。
