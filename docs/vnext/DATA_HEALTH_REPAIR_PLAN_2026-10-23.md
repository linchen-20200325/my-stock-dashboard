# Data Health 修復計畫（2026-10-23）—— DEC-074 B 落地批＋其餘 🔴 分批提案

> **狀態**：~~**提案（Proposal）**；⛔ **非 Approved**、⛔ **非動工授權**（`CLAUDE.md` §-1；DEC-002、DEC-015）；**範圍待客戶裁示**（`CLAUDE.md` §8.4 step 4：範圍問客戶、做法自己定）。~~（superseded 2026-10-23，有意識的修改，不是漏刪 —— 舊句在提案當下正確；客戶已裁示範圍，故以下一行為準；本檔其餘內容仍是「做法」提案、未改）本檔只整理「做什麼、先做哪個、哪裡要先問」，⛔ 不改產品 code、UI、公式、門檻、資料來源。
> 📌 **2026-10-23 客戶裁示（DEC-075）：D-1=(a)；批 A＋1' 已指派；批 2 暫不併 VN1-PG**（`docs/DECISIONS.md` DEC-075 逐字原文；DR-2026-10-23-3）。現行狀態：**批 A（第 1 節，含 1.3.2）＋批 1'（第 2.1 節三項）＝動工授權**（#908 合併後為下一批；批 A High，開工前依 DEC-073 Gate 自判）；批 2～4、`DH-LAMP-STALE`、第 2.5 節仍為提案；批 2／VN1-PG 邊界待批 A＋1' 完成、獨立 QA、CI、main verification 後重評。⛔ 第 1.6 節「需線框」項仍受 DEC-003 gate；⛔ 批 1' 不得新增資料來源或改變投資公式；⛔ 第 0.3 節未驗證清單仍須實作前重查。
> **用途**：把三組唯讀踩點／稽核（見第 0.2 節）收斂成一份可送客戶裁示範圍的計畫；實作批開工前仍須客戶指派，並依 DEC-073 先過 Model／Effort Gate（`PROJECT_RULES.md` 第 9.0 節）。
> **待辦落點**：只在 `docs/BACKLOG.md` 5.1.7（`DH-*`）與 Decision Register（`DR-2026-10-23-3`）；摘要見 `docs/PROJECT_STATE.md` §27；下一 Decision Gate 指標見 `docs/HANDOFF.md` 第 0 節。
> **量測**：2026-10-23；分支 `ccr-310717b7-37xwl6`（工作樹 HEAD `1196bb7f`＝ merge of main `50411d33`；稽核組 NIT-A4 更正，A 組原寫「＝ main `50411d33`」為近似）。本檔**不寫行號**（`CLAUDE.md` §8.2.A.0 規則 1），**不寫「共 N 處」**（規則 2）；凡「0 讀者／唯一／只有」類全稱句一律為 **grep 結論、未 AST 追動態 import**，只能當待驗事項。
> **慣例**：append-only；本檔之後若有裁示或更正，在對應段落下加 📌 註，不改原文。

---

## 0. 狀態、依據、來源、未驗證清單

### 0.1 依據

| 依據 | 本計畫怎麼用 |
|---|---|
| **DEC-074**（客戶 2026-10-23；`docs/DECISIONS.md`） | 批 A 的不變量全部由此導出：代理廣度不得計分；缺真實 breadth 不得當 0／中性／正常；受 breadth 影響且無法依既有正式規則可靠計算的健康分 →「⬜ 未評估／資料不足」；不得自創權重重新正規化；不得為「有結論」補結論；⛔ 非實作授權；判定範圍未逐項列舉，多個合理讀法時須停下裁示（→ 本檔 D-1）。 |
| **DEC-062 Q5**（代理值只顯示、不計分；同樣適用總經彙總燈） | 批 A 的「可以顯示、不可計分」（I-5）；批 2 的 BIAS240／PCR 估算值不計分語意已由此裁示，**不另送題**。 |
| **DEC-073**（Model／Effort Gate） | 每批 Effort 標示（`PROJECT_RULES.md` 9.1 分級）；批 A 判 High（稽核組 CONFIRMED）；開工前**仍須重判**。 |
| **`CLAUDE.md` §1**（Fail Loud, Never Fake；§1.A 四條） | 每條 🔴 的修法都是「假值 → 顯式缺值＋旗標＋下游明示未評估」，⛔ 不得改成另一個猜值；批 1' 的 `MISSING_STALE` 若未同步缺值原因對映會把「資料過期」畫成「程式要修」（§1.A 第 4 點），故列為同批必做（MUST-B1）。 |
| **`CLAUDE.md` §8.4 step 4** | 本檔第 3 節以「為這次必須改 vs 建議但可延後」送客戶決定**範圍**；哪些屬必須改是技術判斷（總管拍板），客戶只決定要不要連建議項一起做；送題附推薦方案、不只丟選項（v3 §03-1「嚴禁拋選擇題」與 §8.4 step 4 的併讀見 `CLAUDE.md` §-1.5.F 判定 8）。 |
| **DEC-003 ①／`CLAUDE.md` §-1.5.A-8** | 每批的線框判定：改變畫面結構才需線框；把假值改成「⬜ 未評估」＝修正錯誤，不需線框。 |
| **DEC-019**（舊 UI 凍結） | 只在舊 UI 檔內的 bug 登記不做；共用層根因只在新 UI 確實依賴時修。批 1' 的 `DH-TWII-MA200` 與 `DH-FIN-HEALTH-CF`(a) B 項因此被稽核組否證（見第 2.1 節）。 |

### 0.2 來源（三組，皆唯讀、零 diff；**皆單組，未經第三組驗證**）

| 組 | 產出 | 本檔採用方式 |
|---|---|---|
| **A 組**（架構踩點：DEC-074 B 落地） | 資料流／呼叫鏈、既有契約、最小改動 13 條、D-1～D-4、線框判定、預期紅測試、新測試、Effort High | 第 1 節主體；**凡稽核組 REFUTED／MUST 者以稽核組為準**（已逐條套用，見第 1.4 節） |
| **B 組**（架構踩點：其餘 🔴 範圍與順序） | 25 條逐條分類、批 1～4＋不排批、依賴圖、崩點彙總 | 第 2 節主體；批 1 依稽核組收斂為批 1'（第 2.1 節），其餘批次保留並套用稽核組的符號／行為更正 |
| **QA 組**（獨立稽核） | A 組 6 項承重宣稱＋新發現 MUST-A1／SHOULD-A2／A3；B 組 5 項承重宣稱＋批 1 逐項判；Effort 判定；重疊／衝突表 D；MUST／SHOULD／NIT 清單 | **凌駕前兩組**：所有 REFUTED 與 MUST 已套用；SHOULD／NIT 已套用於對應段落 |

### 0.3 未驗證清單（`CLAUDE.md` §-2 規則 6；⛔ 不得作為實作批前提，實作前須重查）

1. **撰寫組自身**：本檔由撰寫組單組整合，**未實跑任何測試、未開檔逐一驗證三份輸入引用的符號**；只 grep 抽查下列符號存在：`macro_state_locker.get_macro_state` 內 `_wr_ok`、`page_today.READINESS_REASON_TO_MISS`、`tests/test_batch_z60.py::TestVerdictIdleExitIsRetry::test_warroom_health_none`／`_assert_retry`／`TestDegradedRegimeExitIsRetry::test_degraded_with_health_none_warroom`、`tests/test_p1b_fabricated_defaults.py::TestHealthRenormalisesInsteadOfFabricating::test_missing_jqavg_uses_renormalised_weight_not_neutral_50`、`tests/test_review_fixes_v19_84.py::test_adl_path_no_pct_keys`／`test_fallback_path_no_pct_keys_and_flagged`。
2. **A 組自揭**（原 §7）：「health None 時無下游會崩」只實讀 `compute_position_throttle` 四個 caller 與 `build_allocation_decision`，其餘消費者 grep 列舉未逐一開檔；「`jingqi_info['avg']` 計分消費者只有 `calc_traffic_light`」為 grep；「`is_proxy` 只有 `section_short` 讀」為 grep；預期紅測試清單**未實跑**；`test_batch_z8`／`z65`／`z66b` golden 對 health None／檔案位階的具體斷言未開檔；AUD-C22、DEC-037 原文未讀（先例型態取自實作）；`fetch_twse_breadth` 可達性未驗；`src/ui_v2/**` 未逐檔讀；推播腳本僅 `push_holdings_daily` 開檔。
3. **B 組自揭**（原 §6）：「新 UI 無 scoring_engine import」「無讀 `ma200`」「`li_retain_meta` 在 `page_today` 0 命中」「`macro_snapshot` 無 `@monitored`」「`PRICE_CLOSE_FFILLED_ATTR` 唯一讀者」「`src`／`shared` 無借券來源」皆 grep；`DH-EXPORT-LABEL` 來源鏈與出口燈 stale 路徑未讀 `fetch_export_block`；`DH-FIN-HEALTH-CF` 累計 vs 單季口徑、`DH-357-DIV-FIELD` FinMind 欄名**未以真實 API 驗**（沙箱 403）；`yf_proxy.cached_history` 的 `auto_adjust` 預設未確認；`DH-ETF-FFILL` 報酬段 as_of 未逐行確認；`DH-HEALTH-HISTORY` workflow cron 行未讀；「測試 N 檔提及」為 `grep -l` 計數、不等於會紅的測試數。
4. **QA 組自揭**（原 §六）：`test_batch_z8`／`z65`／`z66b` golden 未開檔；`fetch_yf_ohlcv('^TWII','9mo')` 實際根數未量（無網路）；FinMind `CashFlowsFromOperatingActivities` 口徑未驗；「0 讀者／0 import」皆 grep。
5. **本檔自己下的判斷**（單組，未經第二組驗）：第 1.5 節 D-1 送題文的措辭、第 2 節把 `DH-FIN-HEALTH-CF`(a) 放批 3 而非併 (b)（稽核組 MUST-B2 原建議「併 (b)」，總管指示放批 3／High，兩者皆為 High、僅批次歸屬不同）、第 3 節推薦範圍、第 4 節 `ruleset_hash` 合併 bump 的建議。

---

## 1. 批 A｜DEC-074 B 落地（含 `DH-TWII-MA200` 併入）

> 對應 BACKLOG：`DH-GATE-BREADTH`（已裁示 B）、`DH-ADL-PROXY`、`DH-JINGQI-HEALTH`、`DH-TWII-MA200`（併入理由見 1.3.2）。
> **Effort：High**（A 組判定，稽核組 CONFIRMED；9.1 命中「核心投資語意／判斷公式」「重新定義評分或投資結論」「L3／資料層重大變更」「多個合理方案需深入權衡」「Point-in-Time correctness」）。開工前依 DEC-073 重判；撰寫組建議模型＝高能力模型（僅供參考）。
> **線框**：批 A 內全部改動判為「修正錯誤／狀態變、非結構變」，**不需線框**（判定表見 1.6）；⚠️ 若實作中出現「新增廣度狀態卡／列、移除油門區塊或 ADL KPI 格、拿掉五桶 `adl` 盞」任一項，即刻脫離本批、須先出線框（v3 §03-2 ①「欄位增減」）。
> **裁示需求**：**D-1**（`DH-GATE-REGIME-FALLBACK`，第 1.5 節）須客戶裁示後才能定案 #12／#11；D-2～D-4 內部拍板、交付報告揭露。

### 1.1 不變量（由 DEC-074 導出，供獨立 QA 驗收）

- **I-1** 任何計分路徑（健康分、大盤評分、五桶燈級）不得吃 proxy breadth 數值。
- **I-2** breadth 缺席 ⇒ 健康分 `None`（⛔ 不是 0、不是 50、不是只剩大盤分重新歸一）。
- **I-3** 健康分 `None` ⇒ 姿態帶不給結論（既有 `build_allocation_decision` 路徑已成立）。
- **I-4** 「⬜ 未評估／資料不足」文案不得暗示「重跑就會有」（`CLAUDE.md` §-2 實證第 3 條：重跑一百次也一樣）。
- **I-5** proxy 值**可以顯示**（DEC-062 Q5），但須帶代理標記。

### 1.2 資料流與呼叫鏈（A 組 §1 實讀；稽核組 A1～A5 **CONFIRMED**）

```
L1  src/data/daily/daily_data_fetchers.py::fetch_adl
      100% 由 yfinance ^TWII 日內漲跌幅推估（每列 is_proxy=True；end=today 不含當日 ⇒ D−1）
      ⚠️ docstring「精確值自動覆蓋」不實（同審計表）
    src/data/macro/tw_macro.py::fetch_twse_breadth（TWSE MI_INDEX 真實單日家數；唯一 production caller 為舊 UI section_short）
        │
L3  src/services/macro_fetch_orchestrator.py::fetch_macro_bundle（_job_adl → bundle['df_adl_raw']）
        ├─► 入口 A  src/services/jingqi_calc.py::compute_and_store_jingqi
        │      df_adl_raw['ad_ratio'].tail(5).mean() → st.session_state['jingqi_info'] 7 鍵（avg/pos/regime/color/label/total/source）
        │      ⚠️ 不讀 is_proxy（稽核 A3 CONFIRMED）；備援「大盤估算」40+up_days×5；第 4 寫入點 section_short 以 TWSE 單日真值寫入
        └─► 入口 B  src/services/market_assessment_apply.py::compute_and_apply_market_assessment(df_adl=…)
               df_adl['ad_ratio'].iloc[-1] → market_strategy.get_market_assessment(ad_ratio=…) → market_regime(ad_ratio=…)
               ad_ratio > MARKET_BREADTH_NEUTRAL_PCT ⇒ score+1、max_score 4→5；⚠️ 不讀 is_proxy、無 ad_ratio_is_proxy kwarg（稽核 A3）
               regime（bull/neutral/bear）由 MA120 三日法則決定、不受 ad_ratio 影響
        │
L2  src/compute/macro/macro_helpers.py::calc_traffic_light(mkt_info, jingqi_info, cl_data, li_latest)
      健康分 = Σ(value_i×w_i)/Σw_i（HEALTH_WEIGHT_JQ=0.6／HEALTH_WEIGHT_SCORE=0.4；shared/signal_thresholds.py）
      ⚠️ 缺任一腿即重新歸一（稽核 A2 CONFIRMED，test_missing_jqavg_uses_renormalised_weight_not_neutral_50 實跑綠、health==75）＝ DEC-074 排除的 (A) 路徑
      兩腿全缺 → health=None → shared/regime_arbiter.py::arbitrate_regime → UNLOADED_VERDICT（regime='unknown'／light='⬜'／source=SOURCE_UNLOADED／is_loaded=False）
      文案 _TL_COPY_BY_SOURCE[SOURCE_UNLOADED] 第 4 句「請按「🚀 一鍵更新全部數據」重新抓取」⚠️ 違 I-4
        │
L2/L3 warroom_summary：舊 UI section_traffic_light／section_state 寫入；新 UI src/services/warroom_apply.py → src/compute/macro/warroom_summary.py::build_warroom_summary（13 鍵 WARROOM_SUMMARY_KEYS，不含 health_partial／缺值原因）
        │
L3  src/services/macro_state_locker.py::get_macro_state(warroom_summary, …)
      _wr_ok = bool(_wr) and _is_finite_number(_wr['health_score'])  ⇒ health None ⇒ warroom 視同不可用
      ⇒ 退第 3 順位 macro_state.json['market_regime']（規則引擎 calculate_system_state，8 項輸入不含 breadth）⇒ source=SOURCE_FILE_RULE_ENGINE、is_loaded=True、health=None、regime=<檔內位階>
      （稽核 A1 CONFIRMED；⚠️ 此時 warroom 的 regime_source 完全不被讀 → MUST-A1，見 1.4）
        │
L0/L3 allocation_service.get_macro_regime()／get_allocation() → shared/allocation_decision.py::build_allocation_decision
      not is_loaded or health is None ⇒ posture='未評估'、icon='⬜'、final_*=None
      ⚠️ 位階（regime）與姿態帶（posture）在 health None 時分家：位階可能仍由檔案給 bull，姿態帶已未評估
        │
消費者（A 組 §1.5 逐一列舉，非窮舉宣稱）：舊 UI handlers／section_*／macro_classroom／etf_tab_portfolio／app.py 置底條；五桶 compute_five_bucket_summary（health 燈 gray，但 jingqi／adl 兩盞仍拿 proxy 值計燈級並進桶 worst-of，違 I-1）；新 UI page_today（卡① _alloc_unloaded_why 出口 EXIT_RETRY_HERE ⚠️ I-4；卡③ classify_macro_contract 在 SOURCE_FILE_RULE_ENGINE 時 UI_DEGRADED 位階照印）／page_find._load_regime（is_loaded 真就套空頭濾網）／page_hold＋dividend_station_service.get_station_macro；AI ai_qa_service／section_news_ai；診斷 reconcile_service／reconcile_panel／data_coverage；通知 push_holdings_daily；cron update_macro_forward_test → macro_forward_test.build_signal_row → data_cache/macro_forward_test/signals.parquet（ruleset_hash payload 不含「breadth 是否計分」旗標）；校準 cron calibrate_macro_traffic／calibrate_health_weights（以 proxy jqavg 校準門檻／權重，方向與本批相反）；Risk Cap Sheet 快照 risk_cap_apply／risk_cap_history_service（VALID 判定程式路徑零 health／breadth 依賴，稽核 A5 CONFIRMED；NIT-A5：docstring 有字面命中）
```

### 1.3 既有可沿用契約（不自創權重、不發明第二種機制）

**結論：三層都已有型別／契約，本批不需要新權重、也不需要新 enum 體系**（A 組 §2，稽核組 A4 CONFIRMED 先例可鏡像）。

| 層 | 既有表示 | 可沿用程度 |
|---|---|---|
| L0 `shared/regime_arbiter.py` | `UNLOADED_VERDICT`（`regime='unknown'`／`light='⬜'`／`source=SOURCE_UNLOADED`／`is_loaded=False`）；`REGIME_LIGHT['unknown']='⬜'`；`shared/allocation_decision.REGIME_LABEL['unknown']='未評估'` | ✅ 直接沿用燈色／regime；⚠️ `source` 只有 `unloaded` 一種，分不出「沒人算過」與「算過但資料不足」 |
| L2 `calc_traffic_light` | `health: Optional[float]`、`health_partial: bool`、`missing_sources`、`_TL_COPY_BY_SOURCE[SOURCE_UNLOADED]` label 恰為「總經未評估｜資料不足」 | ✅ 型別已 Optional；⚠️ `action` 指引重跑（I-4） |
| L2 `build_warroom_summary` | `health_score: None`、`throttle: None` | ✅ |
| L3 `get_macro_state` | `health: None`、`is_loaded`、`source` | ⚠️ health None ⇒ 退檔案位階（→ D-1） |
| L0 `build_allocation_decision` | `posture='未評估'`、`icon='⬜'`、`final_*=None` | ✅ 姿態帶已不給結論；⚠️ `headline()` 指引重跑（I-4） |
| 五桶 | `classify_danger(None)` → gray；M1B 代理先例「顯示值、燈灰、不進桶」（DL-f1-s17） | ✅ 完全比照 |
| 先例 | `shared/signal_thresholds.M1B_M2_LEG_ENABLED=False`＋`shared/macro_provenance.{is_m1b_m2_proxy, m1b_m2_proxy_badge, m1b_m2_for_scoring}`＋`market_regime(m1b_m2_is_proxy=…)` | ✅ 鏡像做 breadth 三支＋一旗標（DEC-037／批 Z66 型態） |

health None 時：實讀範圍內**無**下游會崩（`compute_position_throttle` 四個 caller 皆有守衛；`build_allocation_decision` 先判 None）；**無**當 0（v19.470 已三態化）；當**中性**者只有 `normalize_regime` 對不認得的值回 `'neutral'`（檔案位階路徑）與 `health_reconcile.compute_method_b_health` 的 `jqavg or 50.0`（已被 gate 擋，另案）；**偷換結論**者＝`get_macro_state` 第 3 順位檔案位階＋`page_find` 濾網＋`page_today` 卡③ degraded 照印（→ D-1）。（以上「無／只有」為 A 組實讀＋grep 結論，見 0.3。）

### 1.3.1 最小改動清單（A 組 §3.1，鏡像 M1B 先例；**已套用稽核組 MUST-A1／SHOULD-A2／A3**）

**為這次必須改（缺一即違 DEC-074）**

| # | 層／檔案＋符號 | 改動 | 稽核組修正 |
|---|---|---|---|
| 1 | L0 `shared/signal_thresholds.py` | 新增 `BREADTH_PROXY_SCORING_ENABLED: bool = False`（docstring 記 DEC-074、復活條件＝正式 breadth 或客戶核准算法）；`HEALTH_WEIGHT_JQ/SCORE` **一字不動**（I-2） | — |
| 2 | L0 `shared/macro_provenance.py` | 新增 `is_breadth_proxy(jingqi_info)`、`jingqi_for_scoring(info) -> Optional[dict]`（proxy ⇒ None）、`breadth_proxy_badge()`；純函式，鏡像 M1B 三支 | — |
| 3 | L3 `src/services/jingqi_calc.py::compute_and_store_jingqi` | 讀 `df_adl_raw['is_proxy']`；主源為代理或走「大盤估算」時寫 `is_proxy=True`（schema-additive 第 8 鍵；`avg` 照算供顯示，I-5）；同步 `tests/test_p0c_breadth_naming.py::_JQ_CONTRACT_KEYS`（7→8）；更新 `section_short.py`「刻意不新增 is_proxy 鍵」註解與其 TWSE 即時 fallback（亦標 `is_proxy=True`，依 D-2） | **SHOULD-A3**：`tests/test_review_fixes_v19_84.py::TestJingqiNoFabricatedKeys::test_adl_path_no_pct_keys` 與同檔 `test_fallback_path_no_pct_keys_and_flagged` 皆為**確定**精確鍵集合比對（`set(info) == _JQ_EXPECTED_KEYS`），新增第 8 鍵時**兩者必紅**（不是「若」），須同步更新契約常數（有意識的變更） |
| 4 | L3 `src/services/market_assessment_apply.py`＋`src/services/market_strategy.py::market_regime`／`get_market_assessment` | `df_adl['is_proxy'].any()`（缺欄視同代理，fail-safe）⇒ 傳 `ad_ratio=None`＋新 kwarg `ad_ratio_is_proxy=True`；`market_regime` 代理時 `signals.append('⬜ 市場廣度 NN.N%（^TWII 估算代理）— 不計分')`、不進分子分母（`max_score` 回 4.0）、**不**列入 `missing_factors`（「代理不計分」≠「缺失」，同 `test_retired_leg_is_not_reported_as_missing` 語意） | 與 `DH-TWII-MA200` 同函式 `get_market_assessment`（稽核 D 表）→ **併入本批**，見 1.3.2 |
| 5 | L2 `src/compute/macro/macro_helpers.py::calc_traffic_light` | `_jq = jingqi_for_scoring(jingqi_info) or {}` 取 `_jqavg`；**`_jqavg is None ⇒ _health = None`**（移除「缺旌旗 → 只剩大盤分歸一」段；`_score_pct` 缺席時的既有處置依 D-3 不動）；`health_partial` 保留 bool，另加 `health_unavailable_reason: str|None`（schema-additive，D-4）；`missing_sources` 文字改「市場廣度（無真實漲跌家數來源；代理值不計分）」 | 稽核 A2：`test_missing_jqavg_uses_renormalised_weight_not_neutral_50` 必紅（斷言 health≈75），改斷言為 None＋`SOURCE_UNEVALUATED_BREADTH`、保留「不是 60＝塞 50」那半 |
| 6 | L0 `shared/regime_arbiter.py` | 新增 `SOURCE_UNEVALUATED_BREADTH = 'unevaluated:breadth_unavailable'` 與對應 `RegimeVerdict(regime='unknown', light='⬜', is_loaded=False)`；`arbitrate_regime(..., unavailable_reason=None)` 在 `health is None and unavailable_reason=='breadth'` 時回它，否則維持 `UNLOADED_VERDICT` | — |
| 7 | L2 `_TL_COPY_BY_SOURCE[SOURCE_UNEVALUATED_BREADTH]` | ＝（`TRAFFIC_NEUTRAL`, '總經未評估｜資料不足', '⬜ 缺真實市場廣度（漲跌家數），代理估算值依 DEC-074 不計分', '在正式廣度資料接上前不做多空判斷；**重新抓取不會改變此狀態**'）；既有 `SOURCE_UNLOADED` 文案不動 | — |
| 8 | 舊 UI `src/ui/tabs/macro/handlers.py::_render_traffic_light` | `health_partial` 段刪「權重已重新歸一化」假敘述，改印未評估原因（只改字，不改版面） | 稽核 A6：同檔 `test_health_partial_flag_is_surfaced` 等若比對字樣則紅，改字樣 |
| 9 | 五桶 `compute_five_bucket_summary` | `jingqi`／`adl` 兩盞比照 M1B：代理時 `classify_danger(None, s)`（灰、不進桶 worst-of），`value_str` 後綴代理徽章，側車 `is_proxy=True` | **MUST-D1**：與 `DH-LAMP-STALE`(a) 同改此函式 readiness 側車 → **批 A 先、批 1' 後**（第 2.1 節） |
| 10 | L2 `src/compute/macro/macro_forward_test.py::compute_ruleset_hash` | payload 加 `'breadth_proxy_scoring': BREADTH_PROXY_SCORING_ENABLED`（hash 必變，帳本才分得出本批前後） | **SHOULD-D2**：與 `DH-MACRO-FWD-ASOF` 的 schema bump 二次翻 hash → 第 4 節 |
| 11 | 新 UI `src/ui/views/page_today.py::_alloc_unloaded_why`＋卡①／卡③ why 文案 | 當原因為「缺真實廣度」時寫「缺真實廣度 → 健康分未評估」且出口**不得**是 `EXIT_RETRY_HERE`（I-4；用既有 `EXIT_OUT_OF_REACH` 或新增「等待資料源」出口常數，屬文案不屬版面） | **MUST-A1（⭐ 本批最重要的稽核修正）**：`page_today` 卡①／③ 走 `get_macro_regime()`→`get_macro_state`，health None 時 `_wr_ok=False`，warroom 的 `regime_source` **不會被讀**，回傳 `source` 只可能是 `SOURCE_FILE_RULE_ENGINE` 或 `SOURCE_UNLOADED`。因此 A 組原寫「當 `regime['source'] == SOURCE_UNEVALUATED_BREADTH`」：**在 D-1(b)（維持現況）下永遠為假、#11 不可達**，應刪除或改走 `tl` 直讀；**在 D-1(a) 下**，必須讓 `get_macro_state` 在 `health_score` 非有限數時**仍讀** warroom 的 `regime_source` —— 這是對 `_wr_ok` 這條 C1 v19.182 守衛（NaN 視同未載入）的**語意變更**，須在 D-1 送題文（1.5）與新測試（1.7 第 5 條）明寫。<br>**SHOULD-A2**：#11 須以**原因**（`SOURCE_UNEVALUATED_BREADTH`）而非「health None」判出口 —— `tests/test_batch_z60.py::TestVerdictIdleExitIsRetry::test_warroom_health_none`／`_assert_retry` 的 fixture 是「F1 三源全敗」（非 breadth 原因），斷言出口**必須**是 `EXIT_RETRY_HERE`、**不得**是 `EXIT_OUT_OF_REACH`；以原因區分可保綠，以 health None 一律改出口則必紅。 |
| 12 | L3 `src/services/macro_state_locker.py::get_macro_state` | **依 D-1 裁示**（1.5）；採 (a) 時：warroom 存在且 `regime_source == SOURCE_UNEVALUATED_BREADTH` ⇒ `regime='unknown'`、`is_loaded=False`、不退檔案位階 —— 須放寬 `_wr_ok` 守衛讓此分支在 `health_score` 非有限數時仍讀 `regime_source`（MUST-A1） | 採 (a) 時 `tests/test_macro_state_canonical.py`／`test_batch_z60.py` 內「health 非有限 ⇒ 不讀 warroom」斷言會翻；`TestDegradedRegimeExitIsRetry::test_degraded_with_health_none_warroom`（health None warroom＋新鮮檔 ⇒ `UI_DEGRADED`＋`EXIT_RETRY_HERE`）是否翻取決於 fixture 是否帶 breadth 原因（以原因區分則可保綠；**未實跑**） |
| 13 | 文件 | `CLAUDE.md` §2.1／`DATASTATION.md`／`SPEC.md` 旌旗／ADL 條目同步「代理不計分」；`docs/BACKLOG.md` 三列結案註記 | — |

**建議但可延後（另批；列出供客戶決定是否連做）**

- `src/compute/health/health_reconcile.py::compute_method_b_health` 的 `jqavg or 50.0`（已被 gate 擋，I-2 精神未破）。
- `recalibrate_macro.yml`／`calibrate_health_weights.yml` 兩個季度 cron 仍以 proxy jqavg 校準 `macro_thresholds.json`／提案權重 —— 建議暫停或在產物加「breadth 腿已停用，本校準不適用」標頭；⚠️ 下一季（2027-01-01）會自動產出一份用代理校準的門檻，**本批至少在 PR 揭露**。
- `shared/macro_buckets.py` `adl` spec 標籤（`VN1-MT-SSOT-ADL-LABEL`）。
- `fetch_adl` off-by-one（`end=today`）與 docstring「精確值覆蓋」不實（`DH-ADL-PROXY` 可自行修復項）。⚠️ 與批 2 `DH-MACRO-FWD-ASOF` 相依：若延後，批 2 須帶條件「D−1 事實未變」；若要在本批做，見第 4 節合併 bump 的理由。
- 真實 breadth 替代來源研究（`fetch_twse_breadth` 可達性、sector_flow cron 讀到 MI_INDEX 的矛盾）—— 研究候選，⛔ 不在本批。
- `conf` 五項中 `'adl'` 仍把 proxy df 當「有回東西」算信心（顯示用，但信心看起來比實際高）。
- `ai_qa_service`／`section_news_ai` prompt 內的代理 `ad_ratio` 加代理字樣。

### 1.3.2 `DH-TWII-MA200` 併入批 A

- **事實**（B 組，稽核 B2 CONFIRMED，條件：`df_index=None` 的 production 路徑）：`src/services/market_strategy.py::get_market_assessment` 抓 `fetch_yf_ohlcv('^TWII', range_='9mo')`，9 個月台股交易日 <200 根（稽核 NIT-B6：「約 179 根」為估算、無法沙箱量）⇒ `ma200 = … else current_price` 恆取現價 ⇒ `market_score` 的 `index_price > ma200` 恆 False ⇒「❌ 跌破年線」。對外只影響 `status`／`confidence`／`result['ma200']`（score／signals 由 `market_regime` 蓋掉）。
- **為何併入批 A 而非批 1**（稽核 MUST-B3／D 表）：(i) 批 A #4 要在**同一函式** `get_market_assessment` 簽名／呼叫處透傳 `ad_ratio_is_proxy`，兩批同函式衝突；(ii) `ma200`／`status`／`confidence` 在 `src/ui/views/**`、`src/services/**`（除 `market_strategy`）、`src/compute/macro/**` **0 讀者**（grep；`ai_qa_service` 不讀 `mkt_info`），唯一消費在舊 UI `section_state`／`etf_tab_ai` → B 組「每條都有新 UI 消費者」在此項**自相矛盾**，依 DEC-019 不足以獨立成批；(iii) 但它是同一函式內「假值替代」的另一處，批 A 既已動該函式，順手改成 `<200 根 ⇒ ma200=None`＋`result['ma200_status']`（`market_score` 年線項「未評估」、`status/confidence` 可 None）屬 A-2「修這次弄到的東西」，不是趁機清全 repo。
- **本批只標未評估、不改抓取窗**（若改 `range_='2y'` 讓 MA200 真算得出來，與 `VN1-PG-L-PIT-GAPS`(a)「^TWII 三條抓取路徑」重疊；DEC-070 盤後版另批）。
- 下游：`tests/test_deprecation_honesty.py` 釘 `status/confidence` key 存在（key 仍在、值可 None）；舊 UI `section_state._above200 = _idx2 > _ma200 if _ma200 else None` 可吃 None（B 組實讀，需驗）；`etf_tab_ai` 列印 `mkt_info` 時 None 會進 AI prompt（舊 UI，只驗不改）。
- Effort：併入後不改批 A 的 High 判定。

### 1.4 稽核組對 A 組的判定摘要（已全部套用）

| 編號 | 內容 | 套用位置 |
|---|---|---|
| A1～A5 CONFIRMED | `get_macro_state` 退檔案位階／`calc_traffic_light` 重新歸一／三入口不讀 `is_proxy`／M1B 先例可鏡像／Sheet VALID 零依賴 | 1.2、1.3 |
| A6 CONFIRMED（含節點名修正） | 四個預期紅測試存在；類名 `TestHealthWeightRenormalisation` 不存在 → `TestHealthRenormalisesInsteadOfFabricating`；`test_degraded_with_health_none_warroom` 所屬類為 `TestDegradedRegimeExitIsRetry`；四者＋`TestVerdictIdleExitIsRetry` 全班實跑 41 passed（現況） | 1.3.1 #5／#12、1.7 |
| **MUST-A1** | #11 在 D-1(b) 不可達；D-1(a) 需改 `_wr_ok` 語意 | 1.3.1 #11／#12、1.5 |
| SHOULD-A2 | 補列 `TestVerdictIdleExitIsRetry::test_warroom_health_none`／`_assert_retry`；#11 以原因判出口 | 1.3.1 #11、1.7 |
| SHOULD-A3 | `test_adl_path_no_pct_keys`、`test_fallback_path_no_pct_keys_and_flagged` 確定精確比對 | 1.3.1 #3 |
| NIT-A4／A5 | HEAD 標示；A5 證據句改「程式路徑零依賴（docstring 字面命中）」 | 檔頭、1.2 末 |

### 1.5 Decision Gate **D-1**（BACKLOG `DH-GATE-REGIME-FALLBACK`；⭐ 承重，送客戶裁示）

> 依 DEC-074 第 5 點「有多個合理讀法時須停下裁示」與 `CLAUDE.md` §-1.5.A-4 判準（客戶能用業務語言回答者才請示）。送題格式依 `PROJECT_RULES.md` 第 4 節：業務語言＋總管推薦＋具體原因，可一鍵決策。⛔ 不得由總管默默選 (b)；⛔ 裁示前 #12／#11 不得實作。

**問題（業務語言）**：當總經健康分因為**缺少真實市場廣度（漲跌家數）**而顯示「⬜ 未評估／資料不足」時，📊 大盤頁與持股頁上的**市場位階**（多頭／中性／空頭）是否也一併顯示 ⬜ 未評估？還是允許退回另一套「規則引擎」（`macro_state.json`，由 VIX／PMI／M1B／M2／BIAS240／PCR／期貨淨空算出的曝險分級，**不含廣度**）給出的位階，並標「門檻已失準」？

**兩案與影響**：

| 案 | 內容 | 對客戶可見的影響 | 技術面（內部，列出供透明） |
|---|---|---|---|
| **(a) 位階一併 ⬜**（**總管推薦**） | warroom 存在且健康分未評估原因為「缺真實廣度」時，位階＝未評估、`is_loaded=False`，**不退**規則引擎位階 | 在正式廣度到位前：大盤頁位階卡常態 ⬜；🎯 找標的頁的空頭濾網**不套用**（走既有「未評估不套用、L3 註記」路徑）；🛡️ 持股頁位階／姿態帶未評估；AI 問答回「未評估」提示。系統風險上限（Risk Cap）**不受影響**（其 VALID 判定與位階／健康分無關，稽核 A5） | 需放寬 `get_macro_state._wr_ok`（C1 v19.182「NaN 視同未載入」守衛）讓 health 非有限時仍讀 warroom `regime_source`（MUST-A1）；`tests/test_macro_state_canonical.py`／`test_batch_z60.py` 相關斷言依裁示更新；AUD-C22「位階第 3 順位來源本批不動」的語意會被改寫（A 組未讀 AUD-C22 原文，需第二組對照） |
| **(b) 維持現況** | 健康分 ⬜，但位階退到規則引擎位階並以「degraded／門檻已失準」顯示（新 UI 卡③ 現行行為） | 大盤頁仍印出一個位階結論（來自不含廣度的另一套模型），持股頁 `loaded=True` 但姿態帶空；找標的頁濾網照用檔案位階 | 不動 `_wr_ok`；#11 不可達（刪除或改走 `tl` 直讀）；AUD-C22 語意不變 |

**總管推薦：(a) 位階一併 ⬜。** 理由：
1. DEC-074 原文「不得因為產品希望『有結論』而補出投資結論」—— 規則引擎位階是**另一套模型**頂替紅綠燈結論，形同補結論。
2. 退檔案位階會**靜默換掉結論來源**：畫面上的位階從「健康分仲裁」變成「規則引擎曝險分級」，客戶看不出差別。
3. 送題 `DH-GATE-BREADTH` 時總管已向客戶明示「B 會讓 📊 大盤頁失去結論」，客戶仍選 B；新 UI 若照印 degraded 位階，等於把 B 的後果偷偷縮回。
4. (b) 的理由仍然成立（規則引擎不依賴 breadth，屬「既有正式規則」），但它改寫的是「位階來源優先序」這個使用者看不見的語意，與 DEC-074 B 精神相悖；且 AUD-C22 只說「本批不動」，不是「永遠正確」。

**客戶只需回答**：(a) 或 (b)。

> 📌 2026-10-23 裁示（DEC-075，append-only）：客戶選 **(a)**；(b) 不採用。客戶原文補充的邊界：「不允許在使用者無法清楚辨識的情況下，靜默 fallback 到另一套規則引擎產生位階結論」「缺資料不得為了維持畫面結論而補結論」。#12／#11 解除封鎖（隨批 A 實作）；`_wr_ok` 守衛語意改法、測試斷言更新、AUD-C22 語意改寫見 DEC-075「(a) 的技術落點」。

### 1.5.1 內部拍板項（交付報告揭露，不請示）

- **D-2**：`section_short` 以 TWSE 即時真實家數（單日，非 5 日均）寫入 `jingqi_info` 是否計分？推薦**不計分**（非正式口徑；客戶原文「依既有正式規則可靠計算」—正式規則是 5 日均），亦標 `is_proxy=True`。
- **D-3**：大盤評分缺席而旌旗（真值）存在時是否維持 v19.177 歸一？推薦**維持不動**（非「受 breadth 影響」；本批不擴大範圍）。在正式 breadth 到位前此分支不可達（jqavg 恆 None）。`tests/test_p1_unknown_vs_bearish.py::test_missing_score_renormalises_weights` 因此可保綠。
- **D-4**：`health_partial` 鍵保留 bool（forward-test schema v2 已有此欄）並另加原因鍵，不改既有鍵語意。

### 1.6 線框判定（DEC-003 ①／`CLAUDE.md` §-1.5.A-8）

| 改動 | 判定 | 理由 |
|---|---|---|
| 燈號卡 label／action／sub 文案換成未評估原因（舊 UI `handlers`、L2 文案表） | 修正錯誤，不需線框 | 既有欄位、既有卡；把「請重抓」假指引修回誠實敘述 |
| 健康度數字 `--`／⬜、姿態帶「未評估」、置底條不印持股% | 不需線框 | 既有 None 路徑，現在會常態觸發 |
| 五桶 `jingqi`／`adl` 燈改灰＋代理徽章 | 不需線框 | 完全比照 DL-f1-s17 M1B 先例；盞數／位置不變 |
| 新 UI 卡①／卡③ why 文案與出口常數 | 不需線框 | 既有 Note 欄位換句子；⛔ 不新增 fact 列 |
| 旌旗值旁加「代理」字（`section_overview`／`macro_stock_link`／`app.py`） | 不需線框 | 既有 `source != 'ADL'` 徽章邏輯擴大到 'ADL'；同一格 |
| 位階卡在 D-1(a) 下改顯示 ⬜ | 不需線框（狀態變，不是結構變）；**但 D-1 本身需裁示** | — |
| `DH-TWII-MA200` 年線項改「未評估」 | 不需線框（舊 UI 顯示值） | 假值→未評估 |
| **新增**「廣度資料狀態」獨立卡／列、今天頁多一個 fact 列 | **需線框** | v3 ①「欄位增減」 |
| **移除／合併**舊 UI「🎚️ 建議持股油門」區塊或 ADL KPI 四格 | **需線框** | 視覺元件增刪 |
| 五桶把 `adl` 盞**拿掉** | **需線框**（改標籤字＝不需，但屬 `VN1-MT-SSOT-ADL-LABEL` 另案） | 盞數變＝結構變 |

### 1.7 測試（預期紅＋新增；⚠️ 全部**未實跑**，須實作批實跑確認）

**預期轉紅的既有測試**（A 組 §5.1，套用稽核 A6／SHOULD-A2／A3／NIT-A6）：
- `tests/test_p1b_fabricated_defaults.py::TestHealthRenormalisesInsteadOfFabricating::test_missing_jqavg_uses_renormalised_weight_not_neutral_50`（斷言 health≈75、≠60、`health_partial is True`）→ 改斷言為 None＋`SOURCE_UNEVALUATED_BREADTH`，保留「不是 60＝塞 50」。
- 同檔 `test_health_partial_flag_is_surfaced` 及 handlers 文案測試（若比對「權重已重新歸一化」字樣）→ 改字樣。
- `tests/test_p0c_breadth_naming.py::_JQ_CONTRACT_KEYS`（7 鍵）；`tests/test_review_fixes_v19_84.py::TestJingqiNoFabricatedKeys::test_adl_path_no_pct_keys`、`test_fallback_path_no_pct_keys_and_flagged`（**確定**精確集合比對）→ 第 8 鍵 `is_proxy` 使三者必紅，更新契約常數。
- `tests/test_market_assessment_apply.py::test_ad_ratio_extracted_from_df_adl_last_row`：fixture 若無 `is_proxy` 欄，在「缺欄視同代理」設計下紅 → 改 fixture（建議採缺欄視同代理，fail-safe）。
- `tests/test_batch_z60.py::TestVerdictIdleExitIsRetry::test_warroom_health_none`／`_assert_retry`（**SHOULD-A2 補列**）：fixture 為 F1 三源全敗、斷言出口必須 `EXIT_RETRY_HERE` → #11 以**原因**區分可保綠；以 health None 一律改出口則紅。
- D-1(a) 採納時：`tests/test_batch_z60.py::TestDegradedRegimeExitIsRetry::test_degraded_with_health_none_warroom`、`tests/test_macro_state_canonical.py`、`tests/test_batch_z65.py`／`z66b` 中「warroom health None ⇒ 退檔案位階」斷言 → 依裁示更新（**未開檔**，A 組揭露 10）。
- `tests/test_batch_z8.py` golden sha、`tests/test_batch_z60.py` 端到端 golden／mutants：取決於 fixture 是否經 `compute_and_store_jingqi` 被標 proxy；本方案**不改** `WARROOM_SUMMARY_KEYS` 13 鍵以降低波及；須實跑。
- `tests/test_p7_macro_forward_test.py`／`tests/test_macro_fwd_test_c12.py`：若斷言 `compute_ruleset_hash()` 固定值 → 本批 hash 必變，更新。
- 應保持綠（設計上以**顯式旗標**判代理）：`tests/test_c1_regime_arbitration.py`、`tests/test_macro_helpers.py`（`jq={'avg': 50}` 無旗標視為真值）、`tests/test_b6a_edu_doc_parity.py::test_jingqi_is_ad_ratio_5day_mean`、`tests/test_p01_macro_refresh.py` ADL 守衛／突變（⛔ 不改那兩行字面）、`tests/test_c3_layering_guard.py`（無新跨層 import）、`tests/test_deprecation_honesty.py`（`status/confidence` key 仍在）。

**新測試（含突變；v3 §03-1「拔掉修復邏輯必須轉為紅燈」）**：
1. L2：`jingqi_info={'avg':55,'is_proxy':True}` ⇒ `jqavg is None`、`health is None`、`light=='⬜'`、`regime_source==SOURCE_UNEVALUATED_BREADTH`、`missing_sources` 含廣度字樣、`health_partial is True`。突變：`jingqi_for_scoring` 換回直讀 ⇒ 紅。
2. L2 文案：`_TL_COPY_BY_SOURCE[SOURCE_UNEVALUATED_BREADTH]` 不含「重新抓取」／「一鍵更新」（I-4 守衛）。
3. L3 `jingqi_calc`：proxy df ⇒ `is_proxy=True`；大盤估算 ⇒ `is_proxy=True`；`avg` 照算。突變：拿掉旗標寫入 ⇒ 紅。
4. L3 `market_assessment_apply`／`market_regime`：proxy df ⇒ `ad_ratio=None`、`max_score==4.0`、signals 含「代理」「不計分」、`missing_factors` 不含「市場廣度」。突變：拿掉 `is_proxy` 判斷 ⇒ `max_score==5` ⇒ 紅。
5. L3 `get_macro_state`（**D-1(a) 時；MUST-A1**）：warroom `health_score=None`＋`regime_source==SOURCE_UNEVALUATED_BREADTH`＋有效 `macro_state.json` ⇒ `regime=='unknown'`、`is_loaded=False`；**另加**：warroom `health_score=None`＋`regime_source==SOURCE_UNLOADED`（非 breadth 原因）＋有效檔案 ⇒ 仍退檔案位階（守住 C1 v19.182 其餘語意）。突變：移除原因判斷 ⇒ 紅。
6. 五桶：`jingqi_info` 代理 ⇒ `details[jingqi]['danger']` 灰、`value_str` 帶徽章、不改桶 level；`adl` 同。突變：拿掉 `classify_danger(None)` 分支 ⇒ 紅。
7. forward test：`compute_ruleset_hash()` 旗標 True/False 下不同；`build_signal_row` 對 health None／icon ⬜ 可落地。
8. 原始碼掃描守衛（同 `tests/test_no_hardcoded_position_pct.py` 手法）：`src/compute/**`／`src/services/**` 內凡讀 `jingqi_info['avg']`／`.get('avg')` 進入計分者必經 `jingqi_for_scoring`；白名單＝顯示用檔。
9. 舊 UI handlers：`health_partial` 訊息不含「權重已重新歸一化」。
10. 新 UI `page_today`：`_alloc_unloaded_why` 在 breadth 原因下不走 `EXIT_RETRY_HERE`；**且** F1 三源全敗（非 breadth）仍走 `EXIT_RETRY_HERE`（SHOULD-A2）。
11. `DH-TWII-MA200`：`get_market_assessment` 傳入 <200 根 `df_index` ⇒ `ma200 is None`、`status/confidence` 不為「跌破年線」假值；突變：恢復 `else current_price` ⇒ 紅。

### 1.8 行為風險（PR 必揭露）

- 本批後、正式 breadth 到位前，**每一輪**健康分都是 None ⇒ 舊 UI 燈號卡常態 ⬜、新 UI 卡①常態未評估、`macro_forward_test` 帳本每列 health None（仍記 `twii_close` 可供日後補算；規則 hash 改變，前後列不可混比）。
- D-1(a)：`page_find` 空頭濾網常態不套用；`page_hold` 卡④／⑤ 位階未評估；AI 問答退「未評估」。
- `risk_cap_apply` 仍每輪寫 `macro_state.json`／`risk_cap_state.json`（Required Core 無 breadth）⇒ 系統風險上限與 VALID 不受影響；D-1(a) 下它不再被當位階來源（只當上限）。`RISK_CAP_RULESET_VERSION` 建議不 bump（本批不改上限規則）。
- `recalibrate_macro.yml` 下一季會用 proxy jqavg 重算門檻 —— 本批至少在 PR 揭露、另批處置。

---

## 2. 其餘 🔴 分批（B 組，已套用稽核組 MUST-B1／B2／B3／D1、SHOULD-B1～B4、NIT-B5／B6）

> 判準（B 組 §0）：Effort 依 `PROJECT_RULES.md` 9.1；線框依 DEC-003 ①／A-8；舊 UI 凍結依 DEC-019；§1 鐵則＝假值→顯式缺值＋旗標＋下游明示未評估。

### 2.1 批 1'｜顯式缺值（低耦合先行）—— **收斂後 Medium 可守版本**

| 項 | 改動面（檔案＋符號） | Effort | 線框 | 稽核組判定與揭露 |
|---|---|---|---|---|
| **DH-FOREIGN-FILL0** | `src/services/macro_fetch_orchestrator.py` FinMind 備援段：`_df_i['buy']/['sell']` 缺值 ⇒ `_net=None`（不再 `fillna(0)`；`unobserved_net` 旗標已存在）；`macro_session_patch`（`_last_inst` 含 None 通路）；`shared/macro_buckets` `foreign_net` 讀值 | Medium（單模組；主路徑 BFI82U 已正確） | 不需 | CONFIRMED 可做；**SHOULD-B4 揭露：新 UI 畫面不變、受益在舊 UI** —— 新 UI 唯一消費者 `page_today` 五桶 `foreign_net` 燈經 `macro_helpers._foreign_net_yi` 的 `shared/inst_net.is_net_observed()` 已把未觀測當缺值（gray）；依 DEC-019「共用層只在新 UI 確實依賴時修根因」此項對新 UI 無行為差異，不宜包裝成「新 UI 受益」。需驗 `tests/test_batch_z36.py`、`test_macro_fetch_orchestrator*`；舊 UI 投信／自營顯示 None 只確認不拋例外、不改 |
| **DH-EXPORT-LABEL** | `shared/macro_buckets.BUCKET_DANGER_SPECS` `DangerSpec("tw_export", "台灣出口訂單 YoY", …)` → 改「台灣出口金額 YoY（海關）」；`shared/edu_tokens`／`EDU_GUIDE` 文案；`data_registry` 註解 | Low（改 label＋教學字；不改值、門檻） | 不需（燈名由錯改對＝修正錯誤） | CONFIRMED：`macro_snapshot.fetch_export_block` docstring「海關出口年增率」、五桶 `_traced("tw_export", "財政部海關出口金額年增率…")` 證明 label 錯；`grep 出口訂單 tests/` 0 命中（無守衛釘字）。⚠️ **業務語意一句話確認**（A-4 判準）：客戶原本要的是「出口訂單」還是「出口金額」？總管推薦：**改名不換源**，教學卡說明兩者差異。來源鏈（stat.gov.tw → MOF）未逐行驗（B 組揭露） |
| ISM 教學 key（關聯 `VN1-MT-SSOT-ISM`，不另立） | `src/services/macro_v2_service._EDU_KEY["ism_pmi"]="NAPM"` → 台灣 PMI 教學 key；`EDU_GUIDE` | **Low**（NIT-B5 降級） | 不需 | CONFIRMED 但嚴重度比 B 組寫的低：`EDU_GUIDE[FRED_NAPM]` 的 `how_to_read` 已於批 Z27 改吃台灣 PMI `§§PMI_*§§` token，**只剩 `meaning`／`historical_anchor`／`pair_with` 三欄是 ISM 文案**。與 `DH-EXPORT-LABEL` 同 dict、同批 |

**批 1' 整批 Effort：Medium**（稽核 SHOULD-C1：剔除 MUST-B2／B3 兩項後再評 Medium 成立；三項皆 Low～Medium、不改公式）。**裁示需求**：只需客戶**指派**＋`DH-EXPORT-LABEL` 一句業務確認（附推薦）。**不需 Decision Gate、不需線框。**

**稽核組否證、自原批 1 移出的三項**（原 B 組批 1 Effort Medium 被 REFUTED：原五項橫跨 ≥7 模組、4 層，且含 High 項）：

| 原批 1 項 | 稽核判定 | 去向 |
|---|---|---|
| `DH-TWII-MA200` | **MUST-B3 REFUTED「有新 UI 消費者」**：`ma200`／`status`／`confidence` 新 UI、L3（除 `market_strategy`）、L2 macro 0 讀者（grep）；與批 A #4 **同函式** `get_market_assessment`（B 組寫「唯一相鄰」屬實但低估：不是不同函式） | **併入批 A**（1.3.2） |
| `DH-FIN-HEALTH-CF`(a) | **MUST-B2 REFUTED「不改公式」**：(i) A／C 項「年化 ×4」＝改公式（`_no_ai_survival` 的 `a_val = ocf/cl*100` → `×4`），且 OCF 單季 vs 累計口徑未以 FinMind 實測 —— 若為累計再 ×4 即雙重放大；(ii) B 項 `insufficient_data: Fail → N/A` 改變 `rule_st` → `no_ai_overall_verdict` 氣長計分（`"Fail": -2` → N/A 0）→ grade／「建議換出」結論變動＝9.1 High；**且 B 項分支在新 UI 不可達**（`page_inspect` 呼叫 `analyze_financial_health("", code, fin_data)` 不預填 `b_item_5y`；只有舊 UI `tab_stock`／`section_financial_health`、L3 `stock_grp_service` 預填）→ DEC-019 | **移批 3／High**（總管指示；稽核組原建議「併 (b)」，兩者皆 High、僅批次歸屬不同，見 0.3 第 5 點）。B 項獨立判為舊 UI 專屬 → 登記不做 |
| `DH-LAMP-STALE`(a) | **MUST-D1 撞批 A**：批 A #9 與本項都改 `macro_helpers.compute_five_bucket_summary` readiness 側車（A 加 `is_proxy`，本項加 `is_stale`／`MISSING_STALE`）；批 A #11 與本項都改 `page_today`（同檔不同區段；寫入端一次一檔，`PROCESS.md` §3）。B 組「不與另組搶同一段程式」宣稱**撤回**。<br>**MUST-B1 缺口**：新增 `MISSING_STALE` 必須同批改 `page_today.READINESS_REASON_TO_MISS`（現只映射 5 個 `MISSING_*`）、`shared/station_specs.MISS_*`／`shared/ui_state.EMPTY_STATE_BY_REASON`、`tests/test_decision_readiness.py`，否則落到 `_miss_why`→`UNKNOWN_REASON_WHY`「readiness 側車沒有交代缺值原因（程式要修）」—— 把「資料過期」畫成「程式壞了」，違 `CLAUDE.md` §1.A 第 4 點。`is_stale` 來源路徑：`macro_core.fetch_tw_pmi` 全敗讀 `_macro_cache_load` 設 `is_stale=True` → `macro_snapshot.fetch_tw_pmi_block` 原樣回 → `macro_info['ism_pmi']` 帶 `is_stale`；`DangerSpec` 無 as_of／stale 欄 | **改排批 A 之後**（可作批 1' 的第二小批，或併批 2；Medium 上緣，跨 L0/L2/L5）。(b)「顯示 as-of」每格加文字＝欄位增減 → 需線框，併 `DH-DATA-CENTER` 線框 |

### 2.2 批 2｜PIT／代理不計分（DEC-062 Q5）—— 與 `VN1-PG-*` 併

| 項 | 改動面 | Effort | 線框 | 依賴／重疊 |
|---|---|---|---|---|
| **DH-BIAS240-EST** | `src/compute/macro/dated_inputs.py::extract_bias240`（讀 `bias_info['is_estimated']` → `value=None, missing_reason="估算值（<240 日）不計分"`）、`macro_engine_inputs._type_check`、`macro_state_locker`（Optional 缺的既有路徑） | High（Risk Cap 輸入；Optional 缺→揭露，DEC-048） | 不需 | 與 `DH-PCR-PROXY` 同型同批；相鄰 `VN1-PG-PIT-CONSISTENCY` |
| **DH-PCR-PROXY** | `src/data/macro/leading_indicators.py` FinMind TXO 法人估算段寫 `選PCR_src='FinMind-TXO-inst-est'`、TAIFEX 段寫 `'TAIFEX'`（schema-additive）；`dated_inputs._extract_li_column`／`_finish_pcr`（估算來源 → 不計分、只顯示） | High | 不需 | `leading_indicators` 測試面大（grep -l 計數，非會紅數） |
| **DH-MACRO-FWD-ASOF** | `scripts/update_macro_forward_test.py`、`shared/macro_forward_test_schema.py`（`SIGNAL_COLUMNS` 加 per-leg as_of 欄）、`macro_forward_test.build_signal_row`；append-only、不回填舊列（DEC-028） | Medium | 不需（只寫不讀） | 依賴 `fetch_adl` off-by-one 定案（否則「D−1」事實會變）；**SHOULD-D2：schema bump 會二次翻 `ruleset_hash`** → 第 4 節 |
| **DH-REFRESH-STALE** | `macro_refresh_service`（失敗步驟 → pop 該 key 或寫 `<key>_meta={stale:True, since}`）、`macro_session_patch`（通用 retain_meta）、`page_today`／`risk_cap_gate`（讀 meta）、`macro_engine_inputs`（stale → DatedValue 缺值） | High（跨 L3→L5 session 契約；PIT 一環） | 「沿用 X 輪前」每格文字＝欄位增減 → 需線框；最小版「失敗腿改 ⬜ 未評估」不需 | 稽核 B5 CONFIRMED docstring「刻意不做 `_macro_session_reset()`」。**與 `VN1-PG-PIT-CONSISTENCY` 高度重疊** → 併入該實作批或排在其後，避免兩套 as-of 機制 |
| （VIX／MA5，關聯 `VN1-PG-VIX-ASOF`／`VN1-PG-PIT-CONSISTENCY`） | 由該實作批負責 | High | 不需 | **本計畫不另排** |

**批 2 Effort：High**。**裁示需求**：需客戶**指派**（會改 Risk Cap 分數；語意已由 DEC-062 Q5／DEC-070 裁示，不另送題）。**排在 `VN1-PG-VIX-ASOF`／`VN1-PG-PIT-CONSISTENCY` 實作批同期或之後**，共用 as_of 機制。

### 2.3 批 3｜L1 契約（個股／ETF 資料欄位）

| 項 | 改動面 | Effort | 線框 | 稽核組更正 |
|---|---|---|---|---|
| **DH-357-DIV-FIELD** | `src/data/stock/app_stock_fetchers._fetch_dividend_data_body`（欄名清單改 FinMind 正式欄 `CashEarningsDistribution`／`CashStatutorySurplus`；去掉「第一個數值欄」猜欄；查無正式欄 → 缺值不猜）；tests fixture 改真實欄名 | Medium（單模組欄位對映；影響 357 判讀值 → QA 用真實回應驗） | 不需 | **前置：FinMind 欄名探針**（沙箱 403；需能連網的 Actions log-only run） |
| **DH-KLINE-ADJ** | `data_loader.StockDataLoader` FinMind 備援段標 `attrs['price_basis']='raw'`（沿用 `etf_fetch.PRICE_BASIS_ADJUSTED` 慣例）；`picker_fetcher` 同；`page_inspect` 讀 attrs 改「一律用還原價」文案為動態 | Medium～High | 文案動態化不需；K 線卡加「未還原」徽章＝新增元件 → 需線框（併資料中心） | `yf_proxy.cached_history` 的 `auto_adjust` 預設未確認；停牌偵測另案（`VN1-C-CALENDAR`） |
| **DH-INST-FILL0** | `data_loader.StockDataLoader`（`fill_cols` 與 `numeric_cols` 兩層 `fillna(0)`，含 OHLC／融資融券；加 `is_imputed_<col>` 旗標欄或保留 NaN＋attrs）；`stock_chips_service`；`scoring_engine.calc_chip_score`／`chip_score`；`shared/chip_*` 連續性 | High（L1 核心契約；評分與籌碼訊號是投資語意輸出） | 不需 | **SHOULD-B1 改寫**：稽核沙箱實跑 `calc_chip_score` —— 外資尾 5 日含 NaN → `pd.Series.sum()` skipna → 回 **40.0**；全欄 NaN → `sum()=0.0`、`iloc[-1]` 比較 False → 回 **0.0**（不是 NaN、不是 50）。⚠️ 實況比 B 組寫的更糟：NaN 被**靜默當 0 分**，無任何 NaN 傳播可被下游察覺 → 同批改法須先定義「缺值 → 分數 None」契約，而非只擋 NaN。「必須同批改 `calc_chip_score` 與 `stock_chips_service`」結論仍成立 |
| **DH-ETF-FFILL** | `src/data/etf/etf_fetch._fetch_etf_price_max_cached`（拿掉整張 `df.ffill()`，或只 ffill 非尾端且 attrs 標 `is_imputed`）；`etf_calc.calc_total_return_1y` 等 `iloc[-1]` 函式；L3 消費者 | High（L1 共用取價契約；尾端 NaN 不補＝「現價」語意改變） | 不需 | **SHOULD-B3 更正消費者名單**：`src/ui/views/page_hold.py` 對 `fetch_etf_price` 唯一命中是 docstring、**無直接呼叫**；新 UI 經 L3 `portfolio_deep_service`（VaR，`PRICE_CLOSE_FFILLED_ATTR` 唯一讀者）／`dividend_station_service`／`watchlist_health_service` 間接消費。直接消費者中新 UI 0、L3 服務 5 檔、舊 UI 5 檔（grep）。改法：每個消費者改「最後有效收盤＋其日期 as_of，落後 >N 交易日 → 未評估」（可沿用 `shared/freshness_policy.assess_daily`）；守衛 `tests/test_etf_price_basis_invariant.py`、`test_batch_z48*` |
| **DH-REVENUE-ZERO** | `src/compute/screener/shortage_screener._score_revenue_yoy`／`score_shortage`／`ShortageScore`（加 `missing_factors`、`total` 改「N/4 可評估」或未評估）、`_tier_from_total`；`shortage_screener_service`；新 UI `page_find` 讀 tier（需「未評估」桶） | High（核心選股計分） | 不需 | 三態公告日來源另為研究候選，本批不做 |
| **DH-FIN-HEALTH-CF**(a)（自原批 1 移入） | `financial_health_engine._no_ai_survival` A／C 項年化；B 項 `insufficient_data → N/A`（⚠️ 新 UI 不可達，舊 UI 專屬 → 可登記不做） | High（公式變更；口徑未驗） | 不需 | MUST-B2；**前置：FinMind `CashFlowsFromOperatingActivities` 單季／累計口徑實測**（否則年化可能雙重放大） |

**批 3 Effort：High**。**裁示需求**：需客戶**指派**；需能連 FinMind／Yahoo 的環境做探針（沙箱做不到）。**線框**：只有 `DH-KLINE-ADJ` 徽章若要加 → 併資料中心線框。

### 2.4 批 4｜延後

| 項 | 延後理由 | Effort |
|---|---|---|
| **DH-SCORE-NEUTRAL50** | `scoring_engine` 四函式回 50（稽核 B3-a CONFIRMED）；**SHOULD-B2 更正符號**：repo **無** `calc_total_score`，加權總分函式是 `scoring_engine.stock_score(trend, momentum, chip, volume_score, risk_score, fundamental_score, regime)`，沙箱實跑 `stock_score(50,50,None,50,50)` → `TypeError`（CONFIRMED 行為）；`score_single_stock` 內 `fgms` 已有 `if _scores[k] is not None` 守衛（局部三態化先例）。主要消費在舊 UI（新 UI `src/ui/views` 0 import，grep）→ ROI 低；依賴 `DH-INST-FILL0` 的 chip 缺值契約先定 | High |
| **DH-FWD-RECON** | 對帳面板只在舊 UI；依賴 `DH-KLINE-ADJ` 的 `price_basis` 旗標先落地；基準 period 改 `max`、口徑不一致 → excess=NaN 並標 | High |
| **DH-FIN-HEALTH-CF**(b) | 累計拆單季／`_v()` 查無回 None；需 FinMind 實測＋DEC-047 流程 | High |
| **DH-WHY-FRED-LAMP** | `macro_snapshot` fredgraph 路徑掛 `@monitored('fetch_fred_csv',…)`＋改 `page_why.NAMED_SOURCES.covers` 文字、`MONITORED_FETCHER_COUNT`／`tests/test_p05_why_view.py::TestMonitoredCountIsNotStale` 同步；總管推薦不新增燈（不需線框）；資料中心會重做燈牆 → 併入 | Medium |

### 2.5 不排批

| 類 | 項 | 處置 |
|---|---|---|
| 舊 UI 凍結（DEC-019） | `DH-CHINA-DRAG`（兩行可修但只舊 UI 消費；`macro_helpers` `CHN_PMI` 舊 key 在共用層但新 UI 不依賴）、`DH-SHORT-UNIT`（`leading_indicators._to_yi_mg` 依數值猜單位，住 L1 共用層；待新 UI 接融券時修）、教學頁資料來源地圖（`tab_edu`） | 登記，待 `VN1-MT-LEGACY-GAP` 接回時一併修 |
| 研究候選（新資料源＝Decision Gate） | `DH-SAHM`（無 UNRATE fetcher，紅線一永不觸發）、`DH-SBL`（repo 0 來源，grep） | ⛔ 不升格、不做 |
| 文件批 | `DH-DOC-VIX-CBOE` | 等文件同步批（⛔ 本批不改 `CLAUDE.md`） |
| 送題 | `DH-HEALTH-HISTORY`（機制存在、清單空、排程狀態未讀 yml） | 送題附推薦：**推薦暫不啟用**（新 UI 未讀 `health_history_service`；啟用只累積未被讀的快照） |
| 線框 gate | `DH-DATA-CENTER` | 另送線框；建議一張線框涵蓋 `DH-LAMP-STALE`(b) as-of 欄、`DH-WHY-FRED-LAMP` 燈牆、`DH-KLINE-ADJ` 未還原徽章、`DH-REFRESH-STALE` 沿用上輪標示 —— 一張線框解四條畫面需求 |

### 2.6 依賴圖（誰先）

```
批 A（DEC-074 B＋DH-TWII-MA200；D-1 裁示後）
  ├─► DH-LAMP-STALE(a)（MUST-D1：五桶側車／page_today 序列化在 A 之後；MUST-B1 同批補缺值原因對映）
  ├─► fetch_adl off-by-one（A 列可延後）─► DH-MACRO-FWD-ASOF（否則 D−1 事實會變；hash 二次切換見第 4 節）
  └─► 五桶／ruleset_hash 的「燈號結論改變而 hash 不變」一致性（第 4 節）
VN1-PG-PIT-CONSISTENCY／VN1-PG-VIX-ASOF（另批，as_of 機制）
  └─► 批 2（DH-BIAS240-EST／DH-PCR-PROXY／DH-MACRO-FWD-ASOF／DH-REFRESH-STALE）─► DH-LAMP-STALE(b) ─► DH-DATA-CENTER 線框
DH-KLINE-ADJ（price_basis）─► DH-FWD-RECON
DH-INST-FILL0（chip 缺值契約）─► DH-SCORE-NEUTRAL50
DH-357-DIV-FIELD 前置：FinMind 欄名探針；DH-FIN-HEALTH-CF(a)(b) 前置：FinMind OCF 口徑實測
```

---

## 3. 總管推薦範圍（§8.4 step 4 格式；客戶決定範圍，做法內部定）

**為這次必須改（推薦第一批）＝ 批 A**（含 `DH-TWII-MA200`），**前提：D-1（`DH-GATE-REGIME-FALLBACK`）先裁示**。

理由：
1. DEC-074 已裁示 B，但程式現況仍在計分代理廣度並重新歸一（稽核 A2、A3 CONFIRMED）—— 每一輪畫面上的健康分、位階、姿態帶都建立在客戶已明示不採用的路徑上，**這是目前投資結論不可信的第一根因**（`docs/PROJECT_STATE.md` §25 重大問題 1）。
2. 批 A 沿用既有契約、不自創權重、不發明第二種機制（1.3），改動面雖跨 L0/L2/L3/UI/cron 但每處都有先例（M1B）可鏡像。
3. `DH-TWII-MA200` 與批 A 同函式，分批反而製造衝突。

**建議但可延後（客戶決定是否連做）**：
- **批 1'（Medium）可選加掛**：`DH-FOREIGN-FILL0`、`DH-EXPORT-LABEL`、ISM 教學 key —— 三項與批 A 不撞檔、不需線框；加掛只需一句指派＋出口燈名業務確認。⚠️ 揭露：`DH-FOREIGN-FILL0` 對新 UI 畫面無差異（SHOULD-B4）。
- `DH-LAMP-STALE`(a)：排批 A 之後（MUST-D1），可作批 1' 第二小批。
- 批 2 → 批 3 → 批 4 依序；批 2 併 `VN1-PG-*` 實作批。

**客戶只需決定**：
1. **D-1**：(a) 或 (b)（總管推薦 (a)，1.5）。
2. 是否指派批 A。
3. 要不要把批 1' 一併加掛；`DH-EXPORT-LABEL` 要「出口訂單」還是「出口金額」（推薦：改名為出口金額、不換源）。
4. 批 2 要不要併進 `VN1-PG` 三項實作批一起指派。

⛔ 哪些屬「必須改」是技術判斷，已由總管拍板，不推給客戶；⛔ 本節不是動工授權，指派後仍依 DEC-073 先過 Model／Effort Gate。

> 📌 2026-10-23 裁示（DEC-075，append-only）：四題答案 —— 1. D-1＝**(a)**；2. **指派批 A**（#908 合併後）；3. **同意加掛批 1'**（出口燈名：客戶原文「依實際資料內容修正名稱」，撰寫組讀為採推薦「出口金額（海關）、不換源」，原文未逐字寫「出口金額」）；4. 批 2 **暫不**與 VN1-PG 一起指派（等批 A＋1' 完成、獨立 QA、CI、main verification 後重評邊界）。上句「本節不是動工授權」對批 A＋1' 自本日起不再成立（有意識的修改，不是漏刪；DEC-073 Gate 仍須先過）。

---

## 4. `ruleset_hash` 二次切換風險（稽核 D 表／SHOULD-D2）與處理建議

**風險**：批 A #10 在 `src/compute/macro/macro_forward_test.py::compute_ruleset_hash` payload 加 `'breadth_proxy_scoring'`（hash 翻第一次）；批 2 `DH-MACRO-FWD-ASOF` 在 `shared/macro_forward_test_schema.py` `SIGNAL_COLUMNS` 加 per-leg as_of 欄，依慣例 bump `MACRO_FWD_TEST_SCHEMA_VERSION`，而 **hash payload 含 `'schema': MACRO_FWD_TEST_SCHEMA_VERSION`**（稽核組實讀）⇒ hash 翻第二次。結果：`data_cache/macro_forward_test/signals.parquet` 出現**三段不可混比的規則區間**，且第二段（批 A 後、批 2 前）每列 health 都是 None、價值極低。

**處理建議（總管判斷，單組）**：
1. **批 A 加旗標時一併 bump `MACRO_FWD_TEST_SCHEMA_VERSION`**，並把 `DH-MACRO-FWD-ASOF` 的 `SIGNAL_COLUMNS` per-leg as_of 加欄**一起納入批 A**（純加欄、append-only、不回填舊列，Medium，不改訊號值）—— 這樣帳本只切一次。
2. 前提：`fetch_adl` off-by-one 須在批 A 內一併定案（A 組原列可延後；若併入，批 A 的「D−1」事實固定後 as_of 標示才不會再變）。若客戶不願擴大批 A，則退而求其次：批 A 的 PR 描述**明寫**「本批後 hash 將於批 2 再翻一次，三段區間不可混比」，並在 `shared/macro_forward_test_schema.py` 註解預告。
3. **一致性**：稽核組指出 `DH-LAMP-STALE`／`DH-REFRESH-STALE` 的「stale 不判燈」會改五桶 worst-of 輸入、但不進 hash payload —— 與批 A #10「hash 要能分辨規則」的理由不一致。建議批 A 的 PR 明說：hash 只涵蓋**計分腿**（jq／score／m1b／breadth），五桶燈級不在 hash 射程內；若日後五桶進帳本再另案納入。
4. `RISK_CAP_RULESET_VERSION`（Risk Cap 上限規則）**不 bump**（批 A 不改上限規則，稽核 A5）。

⚠️ 以上為撰寫組依稽核組 D 表所下的建議，**未經第二組驗**；實作批開工前須重讀 `compute_ruleset_hash` payload 與 `MACRO_FWD_TEST_SCHEMA_VERSION` 的現行值確認。
