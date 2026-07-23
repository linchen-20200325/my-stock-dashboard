# CLAUDE.md — 資料完整性憲法（my-stock-dashboard）

> 本檔為 AI 協作的最高行為準則,目標：確保資料**真實、可追溯、計算正確、可重現**。
> 跨領域不變的原則已寫死；**領域相關**的部分由 §0 Bootstrap 依本專案實況填妥。
> 違反本檔任一條視同 bug,須當場修正。
>
> ⚠️ **流程治理 / state 管理 / PR 規範 / Anti-Loop** 屬另一面向,獨立於本「資料憲法」,
> 請見同目錄 `PROCESS.md`（原 Core Protocol v2.0,2026-06-22 並存策略 B 拆檔保留）。

---

## §-1. 工作準則(凌駕 §0~§8)

> 2026-06-24 user 明確要求:**「沒實際 bug / 沒具體需求 → 不要動」**

**AI 提議任何新工作前,必須先驗證**:
1. ❓ 這個項目 user 實際在用嗎?
2. ❓ 是真實 bug 觸發,還是只是 BACKLOG / CLAUDE.md 待議標籤?
3. ❓ ROI 對 user 的工作流程有具體幫助嗎?

**任一答 No → WONTFIX,不該提議**

**禁止的提議模式**:
- ❌ 因為 BACKLOG / CLAUDE.md 寫了就提議
- ❌ 因為「審計清單裡的 TODO」就推
- ❌ 機械式清 TODO list 充數
- ❌ 把「文件待議」當必做項
- ❌ 把「未完成項目?」當作要主動找事做的訊號

**允許動工的觸發**:
- ✅ user 主動要求新功能 / bug fix
- ✅ 跑測試 / 使用時遇到實際錯誤
- ✅ 既有功能維護(security / 依賴升級必要)

**標準 default 回應**:user 沒明確指派時 → **停手等指令**,不主動找事。

---

## §0. 填寫紀錄（首次填寫 2026-06-22；v3 升級 2026-06-22 新增 §8；步驟 4 收尾 2026-06-23）

> Bootstrap 流程全 4 步完成,§0 已從「BOOTSTRAP 紀錄」改名為「填寫紀錄」。
> 完整收尾證據按時序記錄如下。

**步驟 1｜探查專案** — 已完成,三組並行 Explore agent 掃描,涵蓋：
- meta-docs（README/STATE/ARCHITECTURE/SPEC/DATASTATION/STRATEGY_MANUAL/MACRO_CALIBRATION）
- 27 個外部資料來源 endpoint + 單位 + 發布延遲 + 修正風險
- 14 類門檻常數 + 10 大單位陷阱 + TTL 對照表 + 時區/日曆使用

**步驟 2｜填寫待填欄位** — 已完成,以下節次依現有 code 證據填妥（每條附 `file:line`）：
- §2.1 SSOT 5-Tier 27 來源權威分級
- §2.3 Point-in-Time 各源發布延遲 + 修正風險表
- §2.4 Freshness max_age 對照（依 `shared/ttls.py` + macro_core 常數）
- §3.1 Schema 主要 DataFrame 表（待議：是否導入 pandera）
- §3.2 範圍 / 合理性檢查（依 `MACRO_THRESHOLDS` + 領域知識）
- §3.3 反捏造 — 14 類 magic number 盤點（含 SSOT vs inline 標記）
- §3.4 Benford 適用性判斷
- §4.1 8 大單位陷阱
- §4.2 不變量斷言
- §4.4 Welford 適用性判斷
- §4.5 時序對齊（**無**第三方 trading calendar lib）
- §4.6 領域邊界（9 種 TW 股市特有狀態）
- §8 架構先行 — 7 層分層 + 5 條硬規則 + 3 處灰色地帶（v3 增補,evidence: ARCHITECTURE.md §1-§7 + SPEC.md §5）

**步驟 3｜回溯稽核** — 已完成,違憲清單分高/中/低三級;以下 W 系列 + S-H 系列 PR 逐一收斂：
- W1（v18.241 群 A/B/C）：14 處 SSOT 抽出 + EX-CACHE-1/EX-L0-1/EX-AI-1 例外登記（EX-AI-1 v18.399 已退役）
- W3a/W3b（#253）：4 處 inline magic SSOT 抽出 + 收斂 §3.3 表
- W4（#252）：刪死碼 get_nas_proxy 群
- W5-1（#254）：data_loader 5 處 except:pass 收窄 + log
- W5-2（#255）：9 處 except/empty 補 log + 註解
- W5-3（#256）：tw_stock_data_fetcher 加註 §8.2.A EX-CACHE-1+EX-L0-1 例外
- S-H1/H3/H4/H5/H6（#257）：Stock §8.2 5 項違憲全結案
  - S-H4：merrill_clock fetch_pmi_history 下沉 tw_macro（L2→L1 重構）
  - S-H1：data_loader 死碼 safe_fetch_strict 刪除
  - S-H3：etf_fetch 4 處 st.error/warning/session_state → print + module-level dict + accessor
  - S-H5/H6：app.py + etf_dashboard 直呼 L1 → EX-PASSTHRU-1 例外登記（類比 Fund F-H6）

**步驟 4｜收尾** — 已完成。
- §3.3 反捏造 ❌ 0 項（原 14 類 magic number 全 SSOT 化）
- §8.2 高項違憲 0 項（S-H1/H3/H4 真重構；S-H5/H6 EX-PASSTHRU-1 例外登記）
- §8.2.A 例外清單：EX-L0-1 / EX-CACHE-1 / EX-PASSTHRU-1 / EX-OAUTH-1(v18.431 補登)(EX-AI-1 + EX-RENDER-1 已退役)
- 證據：全部 commit history + PR description 保留於 origin/main。

---

## §1. 最高原則：Fail Loud, Never Fake（寧可炸掉,不可造假）

凌駕一切的鐵律。錯誤的數字比沒有數字更危險。

當缺資料、外部呼叫失敗、值異常、或假設無法成立時：

- ✅ **一律 `raise` 並清楚說明**（哪個來源、哪幾筆、為什麼）
- ❌ **禁止**用以下手段讓流程「看起來成功」：
  - `fillna(0)` / 填入任意預設值
  - 無說明的 `ffill` / `bfill`
  - 回傳 dummy / example / 範例資料
  - `except: pass` 或吞掉例外
  - 自行「估一個合理值」當常數
- ⚠️ 任何填補**必須**：(1) 顯式呼叫、(2) 寫入 log、(3) 在輸出帶旗標（如 `is_imputed`）

> **判斷準則**：若你正打算寫一段「讓程式不報錯」的程式碼,先問：
> 「這是在**解決**問題,還是在**掩蓋**問題？」掩蓋 = 違憲。

---

## §2. 資料層（Data Integrity）

### 2.1 SSOT — 單一權威來源

**來源註冊清單 SSOT**：`data_registry.py`（dataset → endpoint → 權威分級對映）+ `macro_core.PMI_SOURCE_REGISTRY`（macro_core.py:1262, v18.240）+ `tw_macro.CBC_MS1_URLS`（tw_macro.py:74）。

**5-Tier 權威分級**（衝突時上層贏,**禁止平均**）：

| Tier | 等級 | 來源範例 | Evidence |
|---|---|---|---|
| **T1** | 官方政府/央行 API | FRED, TWSE OpenAPI, TPEX OpenAPI, TAIFEX, CBC ms1.json, data.gov.tw, MOF, MOPS, BLS, IMF | macro_core.py:51-53, data_registry.py:125-156,228-275 |
| **T2** | 商用聚合 API（帶 API key） | FinMind, DBnomics, Yahoo Finance query1 | data_registry.py:228-275, requirements.txt:16 |
| **T3** | 第三方網站（HTML 抓） | CIER, NDC, StockFeel, MacroMicro, Goodinfo, HiStock/Wearn, MoneyDJ, Cnyes, ISM | macro_core.py:557-558,816,939-1041,1108,1222 |
| **T4** | News RSS（非數值,僅文本） | Google News, Reuters, Bloomberg, CNBC, Yahoo News | data_registry.py:398-425 |
| **T5** | User config / AI | Google Sheets（portfolio）, Gemini API（synthesis only） | gsheet_portfolio.py, ai_engine.py |

**關鍵衝突裁決**：
- **M1B/M2**：CBC（TWD）主、IMF（USD）備 → **禁止跨幣別平均**,IMF 僅作 CBC 全敗 fallback（evidence: data_registry.py:345-350）
- **TW PMI 多源**：依 `PMI_SOURCE_REGISTRY` 順序賽跑,取第一個命中（CIER-EN > data.gov.tw > NDC > CIER首頁 > StockFeel > Cnyes > CIER-cid8 > MoneyDJ,共 8 源）。**不平均**（evidence: macro_core.py PMI_SOURCE_REGISTRY, SPEC.md §4）。⚠️ v19.86 更正：原第 8 順位 FinMind 段（打 dataset `TaiwanEconomicIndicator`）已於 v19.85 拔除 — 該 dataset **不存在於 FinMind**（SDK 2.0.4 枚舉 + 官方文件皆無此名）。FinMind 無 PMI 資料集可替換。⚠️ v19.113 拔除 MacroMicro 段 + CIER cid=21 列表 URL — 探針 run 29182317622（美國 IP + NAS proxy）實錘兩者無回應（macromicro.me host 級攔截、cid21 頁下架）;CIER 段改僅掃首頁。
- **TW NDC 景氣燈號**：FinMind `TaiwanBusinessIndicator`（國發會官方鏡像,含 monitoring 分數 + monitoring_color 燈號 + leading 領先指標）為主 → StockFeel → MacroMicro 備援（v19.85；原「舊源全廢改抓第三方」中的 FinMind 判定為誤診,真名 TaiwanBusinessIndicator 一直可用）
- **US PMI**：FRED（NAPM/ISPMANPMI）> DBnomics（ISM/pmi）> ISM 官網 > MacroMicro（evidence: macro_core.py:557-617）
- **VIX**：Yahoo `^VIX` 主、CBOE CDN 備
- **TW 月營收**：FinMind 主、MOPS 備、Goodinfo 第三（evidence: data_registry.py:276-293）
- **TW 融資餘額**：TWSE 主 → HiStock → Wearn（evidence: data_registry.py:430-449）
- **TW 季報**：FinMind 主、MOPS 備、Goodinfo 第三

### 2.2 Provenance — 血緣追蹤

**目標模型**（template 範例）：
```python
@dataclass(frozen=True)
class DataPoint:
    value: float
    source: str            # 來源識別（e.g. "FRED:CPILFESL", "CBC:ms1.json"）
    fetched_at: datetime   # UTC,抓取當下
    as_of: date            # 資料歸屬日（≠ 抓取日,極重要）
```

**現況**：本專案**尚未**統一以 `DataPoint` 攜帶 provenance,多以 `DataFrame + meta dict / failure token` 方式承載。
- macro 失敗以 token 字串（如 `"FAIL:CIER:timeout"`）回傳供診斷（SPEC.md §4）
- proxy_helper 的 cache layer 攜帶 `X-Cache-*` header 作為來源追蹤
- ✅ **S-PROV-1 v18.246 第 1 階段**:`macro_core.fetch_fred()` 已加 `source` + `fetched_at` 兩欄(schema-additive,既有 caller 無感)。其他 fetcher(`fetch_yf_close` / FinMind / TWSE / CBC 等)後續逐步補上。

### 2.3 Point-in-Time — 防 Lookahead

本專案**無傳統歷史回測**(v18.265 移除 `backtest_engine.py` / `tab_backtest_optimization.py` / `etf_tab_backtest.py` — 因只有現存公司快照 + 短歷史,回頭測必踩 lookahead + 存活者偏誤)。**改採前進式驗證(Forward-test,v19.141~148)**:凍結當下選股 → 事後真實現價對帳 vs 0050(`src/compute/screener/forward_test.py` L2 + `services/forward_test_service.py` L3),**零 lookahead、零存活者偏誤**(都是當下真實決定 + 事後真實現價)。**v19.147 自動化**:`scripts/update_forward_test_freeze.py` + `.github/workflows/update_forward_test.yml` 每月自動凍結(走與選股網畫面同源的 L3 `get_ranked_picks`)→ 落地 git 追蹤 `data_cache/forward_test/picks.parquet`(L1 `forward_test_store.py`);對帳讀「本地 ∪ Google Sheet」去重。解原本「手動 + 只存私人 sheet → 0 樣本」卡關。Macro 拐點驗證(`tw_backtest.py` SPX/TWII 倒掛翻正)+ macro 校準歷史驗算(`scripts/calibrate_macro_traffic.py`,v18.359 F-2 搬入 `scripts/`)仍須遵守 PIT,**禁止 lookahead**。

**各來源發布延遲 + 修正風險**:

| 來源 | 指標 | 發布延遲 | 修正風險 | PIT 對齊鍵 |
|---|---|---|---|---|
| FRED | CPI / NFP | 月後 ~13 天 | **是**(隨後 1-2 月常修) | release_date,**禁止**用 observation_date |
| FinMind | 季財報 | 季後 ~45 天 | **是**(審計修正) | 公告日 |
| FinMind | 月營收 | 月後 ~10 天 | 低 | 公告日 |
| FinMind | 月度 PMI | 月後 ~5-10 天 | 低 | 公告日 |
| CIER / data.gov.tw | TW PMI | 月後第 1 營業日 | 無 | 發布日 |
| CBC | M1B/M2 | 月後 ~5-7 天 | **未明**(待 audit) | 公告日 |
| MOF | 進出口 | 月後 ~8-10 天 | **是**(後續月修 ±5%) | 公告日 |
| TWSE / TPEX | 收盤行情 / 法人 | 同日盤後 ~14:30 TW | 低 | 交易日 + 17:00 後可信 |
| TAIFEX | 期貨 / 選擇權 / PCR | 同日盤後 ~14:00 TW | 無 | 交易日 |
| Yahoo Finance | OHLCV | EOD 16:00 ET ≈ 翌日 04:00 TW | 無 | 交易日(TW 用 T+1 才齊) |
| IMF | M1B 備援 | 月後 1-2 月 | 可能 | 公告日 |

**對齊規則**:
- FRED CPI 用 `release_date` 而非 `observation_date`(修正後值不可回填到過去決策)
- 季財報用「公告日」(45 天後)對齊,**不可**用季末日
- 跨市場 merge_asof 用 backward + tolerance="40d"(macro_core.py:1336)

### 2.4 Freshness — Max Staleness

依 `shared/ttls.py`（SSOT for `@st.cache_data(ttl=N)`）+ macro_core 額外常數：

| TTL 常數 | 數值 | 適用範圍 | Evidence |
|---|---|---|---|
| `TTL_15MIN` | 900 s | Intraday risk metric, optionality PCR | shared/ttls.py:24 |
| `TTL_30MIN` | 1800 s | 三大法人 / 融資 / PCR / 期貨 OI | shared/ttls.py:25, data_config.py:20-21 |
| `TTL_1HOUR` | 3600 s | 報價 / 財報 / macro snapshot | shared/ttls.py:26, data_config.py:22 |
| `TTL_2HOUR` | 7200 s | ETF NAV history | shared/ttls.py:27 |
| `TTL_6HOUR` | 21600 s | 月營收掃描 / 出場訊號 | shared/ttls.py:28 |
| `TTL_1DAY` | 86400 s | 持股 / 評等 / 績效 / 股利歷史 | shared/ttls.py:29, data_config.py:24 |
| `TTL_3DAY` | 259200 s | TW 原始月營收 fetch | shared/ttls.py:30 |
| `TTL_7DAY` | 604800 s | 經理人 / 中文名 | shared/ttls.py:31 |
| `_MACRO_CACHE_TTL_DAYS` | 90 days | PMI / 進出口 fallback 過期快取 | macro_core.py:59 |
| `_FRED_RELEASE_CACHE_TTL_DAYS` | 30 days | FRED 下期發布表 | macro_core.py:63 |
| `_FRED_TTL` | 1800 s | FRED API module-level | macro_core.py:238 |
| `_YF_CLOSE_TTL` | 3600 s | Yahoo Finance close | macro_core.py:302 |

**規則**：超過 TTL 應**重新抓取**;若上游全敗,過期 cache 回傳須帶 `is_stale` 旗標,**禁止**靜默返回。

---

## §3. 驗證層（Validation）

### 3.1 邊界契約（Schema）

**現況**：requirements.txt **無 pandera**,現有資料 schema 散落於各 fetcher 的 dict / df parse 邏輯（如 `data_loader.py`、`scripts/update_macro_history.py`,後者 v18.359 F-2 搬入 `scripts/`）。

**規範**：新增資料流入 / 流出系統的點,**必須**附等效斷言（即使尚未引入 pandera）：

```python
# price_df (股價 OHLCV) — TWSE / Yahoo / FinMind 共通
{
    "date":   DatetimeIndex, ascending=True, unique=True,
    "open":   float >= 0, non-null,
    "high":   float >= 0, non-null,
    "low":    float >= 0, non-null,
    "close":  float >= 0, non-null,
    "volume": int >= 0,   non-null,
}
# 不變量: low <= open/close <= high, low <= high

# pmi_df (TW / US PMI)
{"date": ..., "pmi": float in [30, 70]}   # v18.359 起改自 shared/signal_thresholds.py:139-143(原 merrill_clock.py:107 已下沉 + 該檔已刪)

# macro_df (FRED / CBC / generic macro)
{"date": ..., "value": float, "source": str, "as_of": date}

# monthly_revenue_df (FinMind / MOPS)
{"date": ..., "revenue_twd": float > 0}

# institutional_flow_df (TWSE 三大法人)
{"date": ..., "foreign_twd": float, "trust_twd": float, "dealer_twd": float}
```

⚠️ **待議**:是否將 pandera 加入 requirements 並逐 fetcher 落地 schema?評估 import 開銷後決定（pandera 啟動 ~200ms）。

### 3.2 範圍 / 合理性檢查

| 指標 | 合理範圍 | Evidence |
|---|---|---|
| PMI（採購經理指數） | [30, 70] | shared/signal_thresholds.py:139-143(v18.359 merrill_clock.py 已刪,原 inline 已下沉至此) |
| VIX | [5, 100] | macro_core.py:215 thresholds |
| CPI YoY (%) | [-5, 20] | macro_core.py:216 |
| US10Y (%) | [0, 20] | macro_core.py:217 |
| DXY（美元指數） | [70, 130] | macro_core.py:218 |
| HY OAS (%) | [1, 25] | macro_core.py:220 |
| 殖利率差 10Y-2Y / 10Y-3M (%) | [-3, 5] | macro_core.py:221-222 |
| M2 YoY (%) | [-10, 50] | macro_core.py:223 |
| Fed BS YoY (%) | [-30, 30] | macro_core.py:224 |
| 健康評分 | [0, 100] | macro_helpers.py:24-25 |
| RSI | [0, 100] | config.py:52-53 |
| ATR | > 0 | strategy 層必要 |
| 月營收（個股） | > 0 | (停業時應為 NaN 而非 0) |
| 三大法人單日買賣超 | < 該股 30D 均量 × 5 | ✅ helper + wiring 皆已落地(`src/compute/risk/inst_sanity.py`:`is_inst_net_outlier` + `flag_inst_net_outliers_batch` + `flag_latest_inst_outlier_from_df`,SSOT `INST_NET_OUTLIER_VOLUME_RATIO=5.0`,30 測試)。**v19.135 wire 進 `section_chips_20d`**(舊註「現無 fetcher 同時持 inst_net+30D 均量」已過時 — consumer 端 `df2` 本就同時持 `主力合計`+`volume`,同為張免換價),outlier 時顯示徽章 |

**領域不變量**（calculation-side）：
- OHLC: `low ≤ open/close ≤ high`, `volume ≥ 0`
- date 軸單調遞增
- 6-factor 健康評分 ∈ [0, 100]
- 權重和 ≈ 1.0（健康評分、ETF 權重）

### 3.3 反捏造（Anti-Fabrication）

**禁止 inline magic number**,以下常數**必須**從 SSOT 引入,絕不可腦補：

| 常數類別 | 值 | SSOT 位置 / 現況 | 違憲狀態 |
|---|---|---|---|
| `MACRO_THRESHOLDS`（10 項） | 各 zone 邊界 | macro_core.py:214-225 | ✅ SSOT |
| `YIELD_HIGH/MID/LOW` + `_DEC` | 7.0/5.0/3.0% + 0.07/0.05/0.03 | shared/thresholds.py:21-27 | ✅ SSOT |
| `HEALTH_DEFENSE_THRESHOLD` | 35（[20,60] 可調） | macro_helpers.py:24, macro_thresholds.json | ✅ SSOT + config |
| `BULL_MIN_SCORE` | 4/6（[1,6] 可調） | macro_helpers.py:25 | ✅ SSOT + config |
| `HEALTH_GRADE_A/B_MIN` | 80 / 50 | shared/health_thresholds.py:19-20 | ✅ SSOT |
| `RSI_OVERBOUGHT/OVERSOLD` | 70 / 30 | config.py:52-53 | ✅ SSOT |
| `LEEK_HIGH/LOW` | 35 / 10 | config.py:69-70 | ✅ SSOT |
| `BULLRUN_VOL_THRESHOLD` | 1.3× | config.py:73 | ✅ SSOT |
| ~~`_CPI_THRESHOLD` (merrill clock)~~ | ~~2.0%~~ | ~~merrill_clock.py:56~~(v18.359 F-4 已刪) | ⚪ 退役 |
| `ANNUAL_MA` | 240 trading days | config.py:14 | ✅ SSOT |
| `signal_thresholds.*`（76 個語意常數） | 252 / 健康評分加權 / 4 個 TW 麥邊閾值 / VIX/Foreign futures / ATR%/MA20/合約負債/ETF 折溢價 / Recession logit / PMI 有效範圍 / merge_asof 40d / trend lookback 6 / 個股組合操作狀態燈+多因子評級+入選70+利空信心50 / **scoring_engine 全評分曲線+交易濾網斷點(MOM_/RISK_/RS_/SQ_/FGMS_/LEAD_/CL_/BOLL_/FAKEOUT_/RR_/ATR_STOP_/TIME_STOP_/VCP_/SQUEEZE_/POS_ 共 50 個)** 等 | shared/signal_thresholds.py v18.241→v18.324 | ✅ SSOT（v18.322 補 7 個股組合,詳見 SPEC §12；v18.324 補 50 scoring_engine 全抽,前綴分名防同數字不同義耦合,詳見 SPEC §14） |
| `financial_health_thresholds.MJ_*`（19 個 MJ 門檻） | 現金 25/10 / DSO 15/90 / 100-100-10 / 負債 40/60/70 / 流動·速動 300/150 / 毛利 40 / 安全邊際 60 / 淨利 10 / ROE 15 / 杜邦槓桿 65 / 盈餘品質 100 等 | shared/financial_health_thresholds.py v18.323 | ✅ SSOT（financial_health_engine 6 個 `_no_ai_*` code 端引入；prompt 端由 golden test 釘一致；含 3 漂移修正,詳見 SPEC §13） |

❌ 標記 **0 項**(原 8 項已全數 W3a/W3b 收斂)。

**其他規則**：
- `fillna` / `ffill` / `dropna` 必須顯式呼叫 + log 受影響筆數
- 測試資料與正式路徑物理隔離（pytest fixtures 不可流入 production fetcher cache）
- `except: pass` 一律違憲;`except Exception as e:` 至少要 log + 往上拋或回傳 fail token

### 3.4 統計異常偵測

- **IQR**（穩健,優先用）：**適用** — VIX / HY spread / 個股 vol 為厚尾資料
- **Z-score**（近常態時）：**部分適用** — CPI、PMI 近常態,適用;個股報酬率非常態,**不適用**
- **Benford's Law**：**不適用** — 本專案資料皆官方/聚合 API（FRED/TWSE/FinMind/CBC etc.）,**無人為申報原始資料**。Benford 適用於財報捏造偵測,本專案下游(MOPS 季報)雖含申報資料但已經官方審核,且當前無此偵測需求

---

## §4. 計算層（Computation Correctness）

### 4.1 量綱 / 單位陷阱

| 陷阱 | 描述 | Evidence |
|---|---|---|
| **百分比 vs 小數** | `YIELD_HIGH=7.0`(%) vs `YIELD_HIGH_DEC=0.07`,呼叫端混用 = 100× 誤差 | shared/thresholds.py:21-27 |
| **元 vs 百萬元 vs 億** | FinMind margin 用「元」,macro signal threshold 3400 用「億」(`/1e8` 轉換) | macro_signal_lookback_tw.py:127-131,288 |
| **TWD vs USD** | CBC M1B（TWD）vs IMF M1B（M USD）**禁止平均**,IMF 僅作 fallback | data_registry.py:345-350 |
| **YoY vs MoM** | CPI 用 YoY (%);PMI 用月度 level;merrill_clock 用 CPI YoY | merrill_clock.py:5,133, macro_core.py:216 |
| **名目 vs 實質** | CPI 預設名目;尚未實作實質報酬轉換（待後續需求） | — |
| **交易日 vs 日曆日** | `pct_change(20)` = 20 交易日 ≈ 4 週,**非** 20 日曆日 | macro_signal_lookback_tw.py:167 |
| **TW 時區 vs UTC** | Yahoo Finance EOD 為 UTC;TWSE/CBC/TAIFEX 為 TW 時間 (UTC+8) | app.py:47, daily_checklist.py:131 |
| **點數 vs 百分比** | M1B-M2 gap 用「點/月」差分（diff()）,**非** %  | macro_signal_lookback_tw.py:296 |

**命名規範**：新增變數**必須**編碼單位,例：`rate_pct` / `rate_ratio` / `amount_twd` / `amount_twd_m`（百萬）/ `amount_twd_yi`（億）/ `qty_shares` / `count`。

### 4.2 不變量斷言

```python
# OHLC 鐵則
assert (df["low"] <= df["open"]).all() and (df["low"] <= df["close"]).all()
assert (df["high"] >= df["open"]).all() and (df["high"] >= df["close"]).all()
assert (df["low"] <= df["high"]).all()
assert (df["volume"] >= 0).all()

# 時序
assert df["date"].is_monotonic_increasing, "時序未排序"
assert df["date"].is_unique, "日期重複"

# 健康評分
assert 0 <= health_score <= 100, "score 越界"
assert math.isclose(sum(factor_weights), 1.0, abs_tol=1e-9), "權重未歸一"

# PMI（merrill_clock 已實作）
assert df["pmi"].between(30, 70).all() or df.empty   # evidence: merrill_clock.py:107

# 月營收
assert (df["revenue"] > 0).all() or df["revenue"].isna().all(), "營收應為正或全 NaN"

# 利差合理
assert (us10y_spread.abs() < 5).all(), "10Y-2Y/3M spread 異常"
```

### 4.3 重算對帳（Reconciliation）

**現況雙源備援**已在 §2.1 衝突裁決列明（M1B/M2、PMI、VIX、月營收、融資、季報）。**雙演算法**待落地：
- **健康評分**：目前單一 path（`macro_helpers.compute_macro_health`）,缺對照演算法 → 步驟 3 audit 後補
- **月營收 YoY**：`(本月 / 12 月前) - 1` vs FinMind 預算 YoY 對帳
- **殖利率**：FRED DGS10 vs Yahoo `^TNX` (TNX = 10Y × 10) 對帳

**浮點比較**：**禁止 `==`**,一律：
```python
math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)
np.isclose(a, b, rtol=1e-9, atol=1e-12)
```

### 4.4 數值穩定性

- **log 空間連乘**：cumulative return（(1+r1)(1+r2)...）建議改 `exp(sum(log(1+ri)))`,本專案 backtest 路徑須檢查
- **災難性抵消**：yield spread (10Y-2Y) 兩值尺度接近,計算精度要保留 float64
- **Welford 變異數**：**部分適用** — 現用 pandas `rolling().std()`（內部 Welford-friendly 實作）,**單序列**無需顯式;批次處理 N×T 大序列時可考慮顯式 Welford
- **大數除以小數**：估值倍數（PE = price / EPS）當 EPS 接近 0 時須 guard（return NaN 或 inf,不可 silent ÷0）

### 4.5 時序對齊

**日曆 / 時區決策**：
- **不使用**第三方 trading calendar lib（無 pandas_market_calendars / exchange_calendars 在 requirements.txt）
- 用 Python std `datetime.timezone(timedelta(hours=8))` 統一表示 TW 時間（evidence: app.py:47, daily_checklist.py:131, macro_state_locker.py:352, nas_server.py:66,279）
- **本地時區**：Asia/Taipei (UTC+8)
- **存儲規則**：時間戳一律 UTC（或 TZ-aware UTC+8）,顯示時轉本地

**業務時點**：
- TWSE 同日盤後 ≈ 14:30 TW（17:00 後資料完整）
- TAIFEX 同日盤後 ≈ 14:00 TW
- Yahoo Finance EOD ≈ 16:00 ET → 翌日 ~04:00 TW
- CBC ms1 monthly 月後 ~5-7 天
- GitHub Actions cron `update_macro_history.yml:15` 設 UTC 09:00 = TW 17:00（收盤後）✅
- `recalibrate_macro.yml:15` 每季首日 UTC 00:00（1/4/7/10 月）

**resample 安全性**：
- 已用 `"ME"`（月底）/ `"QE"`（季底）/ `"YE"`（年底）/ `"W-SUN"`（週,錨定週日;v18.461 自 `"W"` 改,right-closed 不變）
- 預設 `closed=right, label=right` — 月底資料 label 為 `"YYYY-MM-31"`,**不會**引入未來資料
- audit 須驗證所有 resample 呼叫的 label/closed 是否一致

⚠️ **無業務還原調整**：本專案不涉及匯率轉換 / 股本回填 / 借券稅後還原,直接用源數據（**不適用** §4.5 業務調整子項）。

### 4.6 邊界條件

**通用**：空資料集 / 單筆 / 全空值 / 欄位剛建立。

**TW 股市 / Macro 領域特有**（必測）：
- **新上市股票**：歷史不足 60 天 → 健康評分應降可信度旗標
- **停牌股票**：連續 N 天無價格 → **不可** ffill,旗標 `is_halted=True` 並 raise 或顯式 skip
- **跨年除權息**：價格跳空 → 用還原價（dividend-adjusted）
- **跌停 0 vol**：有 close 但 vol=0 → 視為有效報價(不可丟掉)
- **月營收三態**：剛公布 / 等公布 / 永久缺（已停業）— 三種狀態須區分,不可一律 `fillna(0)`
- **PMI 多源同月不同數**：依 `PMI_SOURCE_REGISTRY` 順序取第一個命中,**禁止平均**（macro_core.py:1262）
- **多市場休市**：US 假日 ≠ TW 假日,`merge_asof` 跨市場時用 `direction="backward"` + `tolerance="40d"` (macro_core.py:1336)
- **FinMind quota 用罄**：fallback 鏈須完整（MOPS → Goodinfo → HiStock → Wearn）
- **proxy 失效 / 直連 / 407**：`proxy_helper.fetch_url` 已實作降級鏈（NAS Squid → 直連 → fail）

---

## §5. 流程層（Process）

- **冪等性**：同輸入重跑得同結果;重抓不產生重複筆。
- **可重現性**：固定隨機種子、pin 套件版本（注意 requirements.txt 多為 floor-only,backtest 場景須補版本 pin）；歷史運算用**凍結快照**(`data_cache/` parquet）而非即時來源。
- **可觀測性**：每次 pipeline 輸出資料品質指標（缺失率、被填補筆數、outlier 數）,異常告警。
- **效能**：向量化運算,避免隱性逐列迴圈；說明複雜度。

---

## §6. AI 自審清單（每寫完一段主動執行,勿等問）

```
□ SSOT；關鍵數值帶 provenance（source / fetched_at / as_of）
□ 無 inline magic number；常數從 shared/* 或 config.py 引入
□ 缺值顯式處理且 log；無 fillna(0) / 沉默 ffill / except:pass
□ 邊界已測：空集 / 單筆 / 全空值 / 新上市 / 停牌 / 跨年除權息 / 跌停 0 vol / PMI 多源 / FinMind quota / proxy 降級
□ 量綱一致：% vs ratio / TWD vs USD / 元 vs 億 / YoY vs MoM / 交易日 vs 日曆日 / TW vs UTC
□ 無 lookahead：FRED CPI 用 release_date 非 observation_date；季財報用公告日
□ 時序對齊：TW 收盤 14:30 / Yahoo EOD 翌日 / merge_asof tolerance="40d" / resample label 右閉
□ 浮點比較用容差（math.isclose / np.isclose）,非 ==
□ 關鍵指標有第二種算法對帳（健康評分 / 月營收 YoY / 殖利率）
□ 不變量斷言（OHLC / date monotonic / 權重和=1 / PMI∈[30,70]）
□ 向量化,無隱性逐列迴圈
```

最後另外提供：**3 個最容易讓這段程式出錯的輸入**,並寫成測試（單元 + property-based + golden test）。

---

## §7. 新功能動工前對齊

我交付新功能時,你**動手寫程式前**先回答：

1. 資料來源是哪個 endpoint？欄位單位是什麼？（對照 §2.1 表格 + §4.1 單位陷阱）
2. 這資料有發布延遲 / 回溯修正嗎？該用哪個「可用日」對齊？（對照 §2.3 表格）
3. 有哪些邊界要處理？（對照 §4.6 + §3.2 範圍表）
4. 計算式先用**數學式**寫給我確認,再寫程式。

先別寫 code,我們先對齊這四點。

---

## §8. 架構先行 — 涉及新模組 / 多檔案 / 改變資料流時

§7 對齊的是「資料」；本節對齊的是「架構」（模組怎麼切、誰依賴誰、資料怎麼流）。

**觸發條件**：新增模組、跨多檔案、或改變資料流。
**不觸發**：單檔小修、純 bug fix、改字串、typo、版本字串 bump — 直接做,避免儀式性開銷。

### 8.1 通則 — 先設計、自評過度設計、經核准才寫

動工前先提交架構規劃（文字 + 簡單流程圖）,**這一步禁止寫 code**：

1. 這個功能 / 模組的**單一職責**一句話講完。
2. 該切成哪幾個模組 / 檔案？各自職責？
3. **資料流向**：從哪進 → 經過哪幾層 → 從哪出。
4. **依賴方向**：誰依賴誰？有無違反分層？
5. **失敗降級**：外部來源失敗時這個架構怎麼辦（fail loud 還是有備援）？
6. **自評過度設計**：對「當前需求的規模」會不會太重？用不到的抽象 / 分層標「**先不做,等真的需要再加**」。給最簡單能滿足需求的版本,不是最完整的。

### 8.2 本專案分層與依賴硬規則（evidence: ARCHITECTURE.md §1-§7 + SPEC.md §5）

**7 層架構**(由低到高,~21,323 LOC 跨 19 核心模組)：

| 層 | 職責 | 代表檔案 |
|---|---|---|
| **L0 Infra** | 常數 / TTL / 門檻 / 全域 config | `src/config/{config,data_config,persona,stock_names}.py`(v18.359 F-6.1 搬入)、`shared/ttls.py`、`shared/thresholds.py`、`shared/health_thresholds.py`、`shared/fred_series.py`、`shared/roc_calendar.py`(民國↔西元 SSOT,B3 v19.152)、`shared/finmind_subject_aliases.py`(FinMind 科目別名 SSOT,B4 v19.152) |
| **L1 Data** | 外部資料抓取 / 快取 / proxy | `data_loader.py`(B8 v19.155-156 拆分 2545→1734:抽出 `financial_statements_fetcher.py`(MJ 財報,B8-a)+ `data_loader_inst_fetchers.py`(TWSE/TPEX 三大法人 fallback,B8-b),皆同 `src/data/core/`,套件 __getattr__ / import-back 轉發介面不變)、`data_registry.py`、`proxy_helper.py`、`scripts/update_macro_history.py`(cron CLI,v18.359 F-2 搬入)、`scripts/update_forward_test_freeze.py`(前進式驗證每月凍結 cron CLI,v19.147)、`tw_macro.py`、`macro_core.py`、`leading_indicators.py`、`etf_fetch.py`(含 `fetch_etf_close_history`,B7-a 從 UI 下沉)、`tw_stock_data_fetcher.py`、`src/data/portfolio/forward_test_store.py`(前進式驗證本地落地 parquet,v19.147) |
| **L2 Compute** | 純函式運算 / 評分 / 策略 / 風控 | `scoring_engine.py`、`v4_strategy_engine.py`、`v5_modules.py`、`macro_helpers.py`、`etf_calc.py`、`etf_quality.py`、`risk_control.py`、`exit_signals.py`(含 `compute_macd` + `weekly_macd_hist` MACD SSOT kernel,B6 v19.153)、`macro_signal_lookback_tw.py`、`compute/screener/{fundamental_prescreen,shortage_screener,rs_leader_screener,cross_quarter_trends,forward_test}.py`、`compute/risk/risk_contribution.py`(~~`merrill_clock.py`~~ v18.359 F-4 已刪) |
| **L3 Service** | 業務邏輯編排 / AI 整合 / 摘要 | `market_strategy.py`、`ai_structured_summary.py`、`daily_checklist.py`、`macro_state_locker.py`(① 接線 v19.148:`get_macro_state` canonical 總經契約 + `normalize_regime` 中→英)、`services/{fundamental_screener_service,rs_leader_service,shortage_screener_service,forward_test_service}.py`(選股網編排,v19.14x;`fundamental_screener_service.get_ranked_picks` = 畫面/cron 同源排名,v19.147)(~~`ai_engine.py`~~ P5-DEAD-δ 已刪、~~`unified_decision.py`~~ F-4 已刪) |
| **L4 Render** | 圖表生成 / 通用 UI 元件（無 Streamlit container） | `chart_plotter.py`、`etf_render.py`、`ui_widgets.py`、`render/risk_contribution_render.py`(v19.138) |
| **L5 UI Tabs** | Streamlit Tab 級組裝 | `tab_macro.py`、`tab_stock.py`、`tab_stock_grp.py`、`tab_stock_picker.py`、`etf_dashboard.py`、`etf_tab_*.py`(tab_mj_health_diff.py v19.159 孤兒退役) |
| **L6 App** | session_state 路由 + 全域編排 | `app.py`(882 LOC,僅 orchestrator;原 7,300 經 R7/R8/B3-γ/B3-δ 等多輪重構收斂,B9 v19.157 同步) |

**硬規則（violation = 違憲）**：
- ❌ **L1 Data 不得 import streamlit** — 資料層脫離 UI 框架,可單獨測試
- ❌ **L2 Compute 不得 import** `requests` / `proxy_helper` / `FinMind` SDK / `yfinance` — 純函式,無 I/O
- ❌ **L0 Infra 不得依賴任何 L1+** — 被全層 import,須無迴圈依賴
- ❌ **L5 UI / L6 App 不得直呼 L1 Data fetcher** — 透過 L3 Service 取數（cache 才能集中）
- ❌ **跨層上行 import**：L1 不得 import L2/L3、L2 不得 import L3、L3 不得 import L4/L5

**已落地範例**：ETF dashboard 三層分離(SPEC.md §5,v18.182+ 強制)：
```
etf_fetch.py (L1, I/O) → etf_calc.py (L2, 純函式) → etf_render.py (L4, 圖表) → etf_dashboard.py (L5, Tab)
```

**8.2.A 已知例外清單**（豁免 §8.2 硬規則的特定模式,需明確標註理由）：

| ID | 檔:行 | 例外規則 | 理由 |
|---|---|---|---|
| EX-L0-1 | `config.py:126-141` | L0 條件 import streamlit | 限於 `st.secrets` bootstrap 讀 FINMIND_TOKEN；`try/except ImportError` 已護純 .py 環境;**無 UI lifecycle 依賴**(不用 cache_data/session_state)。替代方案(移 L3 + 改函式)會打破所有 caller 介面,ROI 低。v18.241 A1 註記 |
| **EX-CACHE-1** | L1/L2 全層 — **已收齊 9 處 letter compliant**(P2-EX v18.393 → Phase 2 v18.422~426 補 4 處):<br>- `src/data/etf/etf_fetch.py:16-30`<br>- `src/data/macro/leading_indicators.py:19-33`<br>- `src/data/proxy/yf_proxy.py:22-37`<br>- `src/data/core/data_loader.py:19-32`<br>- `src/data/stock/tw_stock_data_fetcher.py:23-38`<br>- `src/compute/etf/etf_calc.py:7-21`(Phase 2 V1 v18.422)<br>- `src/compute/etf/etf_quality.py:18-30`(Phase 2 V2 v18.422)<br>- `src/data/macro/foreign_flow_fetcher.py:24-37`(Phase 2 Batch 3a v18.425,R-UI-FETCH-1 遷出 hot_money)<br>- `src/data/stock/chip_concentration_fetcher.py:38-51`(Phase 2 Batch 3b v18.426,R-UI-FETCH-2 遷出 chip_radar)<br>(另:`src/data/macro/macro_alert.py` 用等價 `_safe_cache` inline 函式) | **`@st.cache_data` / `@st.cache_resource` 條件 import** | Streamlit Cloud cache 是部署架構核心,提供跨 session 共享 + TTL 自動失效,functools.lru_cache 不等價。**允許**在 L1/L2 模組頂部寫 `try: import streamlit as st / except ImportError: 定義 no-op fallback decorator`,前提:**完全不用** `st.session_state` / `st.error()` / `st.markdown()` 等真 UI 呼叫。違反此條件者(原 `data_loader.py:18` 同時用 session_state)**不適用本例外**,須走真重構。**S-H1 v18.244**:data_loader 內死碼 `safe_fetch_strict` 已刪除,現符合 EX-CACHE-1。**S-H3 v18.244**:etf_fetch 4 處 st.error/warning/session_state 已下沉至 print + module-level dict,現符合 EX-CACHE-1。**P2-EX v18.393**:5 處原為無條件 `import streamlit as st`(軟例外)全補 try/except + `_NoOpST` fallback,letter compliant。**Phase 2 V1+V2 v18.422 + Batch 3a/3b v18.425/426**:再補 4 處,etf_calc/etf_quality 收 letter compliance,foreign_flow/chip_concentration 從 L5 UI 遷至 L1 並採同模式。 |
| **EX-OAUTH-1** | `src/data/portfolio/oauth_state.py:25` 無條件 `import streamlit as st` + 用 `st.success` / `st.error` / `st.rerun`(L1 含真 UI 呼叫,超出 EX-CACHE-1 範圍)| **L1 Data 含 OAuth callback flash** | OAuth `handle_oauth_callback()` 屬 auth callback middleware 本質(URL `?code=` exchange → token → flash 訊息 → rerun),類比 web framework session lifecycle。同 EX-L0-1 將 streamlit lifecycle 視為部署框架特性(非業務 UI)。原位於 `src/ui/pages/oauth_state.py`(命名錯誤,從未渲染 UI),v18.400 D4 為解 `gsheet_portfolio.py:50/104/121` 的 L1→L5 反向違憲而搬正至 L1。替代方案(把 callback 拆 L5 UI + L1 client / 或抽 framework adapter)會打破現有 OAuth 流程 + ROI 低。檔內 docstring 已說明,本例外正式登錄於此(v18.431 補)。**升級觸發條件**:若未來新增多 OAuth provider(Twitter / GitHub 等)→ 升級 L4 framework adapter。<br>**v19.159 團隊稽核擴充**:`gsheet_portfolio.py:56/84/110` 讀 `st.session_state`(gsheet_tokens / portfolio_sheet_id)同屬 OAuth session lifecycle(token 取用),納入本例外涵蓋;替代方案(caller 注入 token/sheet_id)打破現有 OAuth flow + ROI 低。 |
| ~~EX-AI-1~~(已退役 v18.399 P5-DEAD-δ) | ~~`ai_engine.py` 全檔 public 函式~~ | ~~LLM 輸出回 **str** 而非 `LLMOutput`~~ | **v18.399 P5-DEAD-δ 整檔真刪**:AST-strict audit 確認 ai_engine.py 5 個 public fn 全 dead(0 production caller / 1 test ref / 1 internal helper 串到另一個 dead fn)。EX-AI-1 例外原文寫「~10+ caller」實際 0 — 例外建立在錯誤前提。真 production AI 走 `app.py:gemini_call` + `ai_fetcher.post_gemini` + `ai_structured_summary.build_structured_summary_prompt` 三條路,本例外正式退役。 |
| **EX-PASSTHRU-1** | UI 直呼以下 L1 fetcher(無對應 L3 業務 wrapper)— **U3 v18.403 全域重盤收齊 25+ 處**:<br>**Module-level import**:<br>- `app.py:62` `from src.data.core import StockDataLoader, _LOADER_VERSION`<br>- `src/ui/etf/etf_dashboard.py:16` `from src.data.etf import ...`<br>- `src/ui/tabs/tab_stock.py:68` `from src.data.core import fetch_bps, fetch_industry_category`<br>- `src/ui/tabs/macro/section_mid.py:17` `from src.data.macro import check_macro_alerts, fetch_macro_snapshot`(v19.159:render_macro_alerts 已歸位 L4 macro_ui_components)<br>**Lazy import**(button click / on-demand):<br>- `src/ui/tabs/tab_edu.py:29,154` `from src.data.proxy import fetch_url`、`from src.data.core import get_categories ...`<br>- `src/ui/tabs/yield_screener.py:33,80` `from src.data.proxy import fetch_url / get_proxy_config`(實際走 L3 yield_screener_service)<br>- `src/ui/tabs/macro/section_short.py:311` `from src.data.macro import fetch_twse_breadth`<br>- `src/ui/tabs/macro/section_state.py:140` `from src.data.macro import ...`<br>- `src/ui/tabs/macro/handlers.py:51` `from src.data.proxy import proxy_helper`(cache clear button)<br>- `src/ui/tabs/tab_stock.py:249,260,2723` `fetch_financial_statements / fetch_stock_news / fetch_5_years_cash_flow`<br>- `src/ui/tabs/tab_stock_grp.py:74` `from src.data.news import fetch_stock_news`(R8 v18.398 新增)<br>- `src/ui/tabs/tab_stock_grp.py` `from src.data.stock.picker_fetcher import fetch_stock_history_1y`(v19.138 風險貢獻分解 button-gated lazy;pass-through、L1 內已 @st.cache_data,同 tab_stock_picker 既有用法)<br>- `src/ui/tabs/tab_macro.py:119,123,130` `src.data.macro` × 2 + `from src.data.news import fetch_macro_news`<br>- `src/ui/tabs/macro/section_news_ai.py:30` `from src.data.news import fetch_macro_news`<br>- `src/ui/tabs/tab_stock_picker.py:282,329,868` `picker_fetcher / core / etf` 3 處<br>- `src/ui/tabs/chip_radar.py:194` `from src.data.proxy import fetch_url`<br>- `src/ui/tabs/hot_money.py:142` `from src.data.macro import finmind_get`<br>- `src/ui/etf/etf_tab_single.py:116,145,684,739` `fetch_etf_zh_name / fetch_etf_manager / is_active_etf / _fetch_news_for` 4 處<br>- `src/ui/etf/etf_tab_portfolio.py:818,1072` `oauth_state(D4 已歸位 L1)/ gsheet_portfolio`<br>- `src/ui/pages/api_diagnostic.py:122` `from src.data.proxy import get_proxy_config`<br>- `src/ui/pages/health_inspector.py:248,275,331,1071,1139,1180` 6 處診斷頁 lazy fetch<br>**L4 Render lazy fallback**:<br>- `src/ui/render/etf_render.py:277` `from src.data.etf import fetch_etf_holdings`(holdings 未預傳時 lazy 抓,P5-B1 漏網 1 處;rationale:fallback 抓比強制 caller pre-fetch 對 ETF 多檔 dashboard 體驗較佳)<br>(註 1:`src/ui/tabs/macro/section_chips.py:22 render_leading_table` 是 render fn 而非 fetcher,合 L4 / 略豁)<br>(註 2:`src/ui/etf/etf_tab_grp_compare.py:25` 已 R4 升 `src/services/etf_grp_compare_service.py`,移出例外)<br>(註 3:`src/ui/tabs/tab_stock_grp.py:37,68-72` 已 R1 升 `src/services/stock_grp_service.py`,移出例外) | L5 UI Tab / L6 App / L4 Render lazy fallback 可直接 import L1 「pass-through 用 + 無 L3 業務值」的 fetcher | §8.2 規則「cache 才能集中」核心理由失效於本場景:L1 模組內已用 `@st.cache_data`(EX-CACHE-1)集中緩存,L3 wrapper 加一層只是 pure pass-through = §8.1 step 6「用不到的抽象」反例。Lazy import 多在 button click / on-demand 場景,延遲 import 避免 module load 時跑全 dependency chain。**升級觸發條件**:若未來新增跨多 fetcher 統一 TTL、多源 fallback chain、或結果後處理 → 升級 L3 service。S-H5/S-H6 v18.244 + P2-EX v18.393 + P5-B2 v18.396 + U3 v18.403 全域重盤決策。 |
| ~~EX-RENDER-1~~(已升級退役 v18.396 P5-B1) | ~~`src/ui/render/etf_render.py:11`~~ | ~~L4 Render 直 import L1 Data fetcher~~ | **v18.396 P5-B1 已重構**:L4→L3→L1 走 `src/services/etf_sector_service.py`(L3 wrapper),封裝 `get_sector_returns(*, refresh=False)` + `get_news_for(...)`。L4 anti-pattern `_fetch_sector_returns.clear()` 已下沉至 L3 service。本例外正式退役,不再需要登錄。 |

**符合 EX-CACHE-1 的標準寫法**(P2-EX v18.393 補 `secrets`):
```python
try:
    import streamlit as st
except ImportError:
    class _NoOpST:
        @staticmethod
        def cache_data(*args, **kwargs):
            # 支援 @st.cache_data 和 @st.cache_data(ttl=...) 兩種呼叫
            if args and callable(args[0]):
                return args[0]
            return lambda f: f
        cache_resource = cache_data
        secrets: dict = {}  # bootstrap 讀 token 用(同 EX-L0-1);無 streamlit 時 fallback 空 dict
    st = _NoOpST()  # noqa
```

新增例外**必須**:(1) 在此表登錄、(2) 對應檔案加註解指回此表、(3) PR 描述附理由。**禁止**未經登錄的潛在「軟例外」。

### 8.3 灰色地帶（待 step 3 audit 確認是否違憲）

- ~~`macro_helpers.py`：分類 L2 但有輕度 I/O（讀 `macro_thresholds.json`）→ audit 看是否該抽 config-loader 到 L0~~ **S-GRAY-1 v18.244 已修**:loader 抽至 `shared/macro_calibration.py`(L0),`macro_helpers` 改 import,介面 0 改
- **`daily_checklist.py`**：跨 L1+L2+L3(fetch + cache + 摘要 + pkl 持久化)→ audit 看是否該拆檔
- ~~**`app.py`**：7,300 LOC,部分計算邏輯可能該下沉到 L2~~ **已收斂至 882 LOC**(R7/R8/B3-γ/B3-δ 拆 AI service / news fetcher / render / fetcher 至 L1-L4;B9 v19.157 同步),現純 orchestrator

### 8.4 做到一半的新增功能 — 先盤點再動

新增功能前 audit pipeline：
1. 現有程式大致分成哪幾塊？資料怎麼流？（對照 §8.2 七層）
2. 哪裡**違反分層**？列檔名 + 行號（§8.3 灰色地帶已點名 3 處,audit 時補上更多）
3. 這次的新功能該放哪一塊？會不會被現有壞結構卡住？
4. 若需要先重構才好加,**分開提案**：「為這次必須改」vs「建議但可延後」,讓我決定範圍,**禁止**自作主張大重構。

核准範圍後才動;一次改一塊,貼 diff + 說明為何不破壞既有行為。

### 8.5 共同收尾

核准後**一次只寫 / 改一個模組**,每完成一個跑 §6 自審。
**禁止中途偏離已核准的架構**；若發現架構需要改,先停下來問。
