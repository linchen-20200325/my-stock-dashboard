# DECISION_RULES — 決策規則「應然」規格（階段 B 第 2 份）
> **這是「應該怎麼判」，不是「哪裡壞了」。** 一個數字進來，系統怎麼判、判成什麼、衝突時聽誰的。症狀清單在 `../stage1/`；缺值根因在 `INDICATOR_SPEC.md` —— 本檔**沿用**其三態（有值／不適用／缺漏），⛔ 不重新定義。已知問題一律**只引編號**（`P1-*`／`N-*`／`D-01`~`D-27`／`A1-*`／`A2-*`）。
> **免責（全檔只講一次）**：本檔**不對任何標的產生買賣建議**，只定義「系統拿什麼數字去比、比完顯示什麼」；code 內的行動字串一律**原樣引用並標為「現行 code 字串常數」**。⛔ 缺失值不得填 0。 ⚠️ **涵蓋門檻（全檔統一用法）**：`有資料因子個數 > 該指標因子總數 × SCREENER_MIN_FACTOR_COVERAGE_RATIO`（**嚴格 `>`**；`shared/signal_thresholds.py`，實作 `src/services/fundamental_screener_service.py:_effective_n`／`len(_present) > _min_present`）。`INDICATOR_SPEC §4` 同一 gate **已改為因子個數版 ＋ 嚴格 `>`，與本檔逐字同語意（兩份已一致；出處 `../audit/INDICATOR_SPEC_REDTEAM.md` A2-1／A2-3）**；⛔ 不另立新常數。⚠️ 單組產出（`CLAUDE.md §-2` 規則 6），複驗狀態見檔尾。**⛔ 本輪零程式碼變更。**
## §1 總經合成
**R1-1 一盞燈進不進分母：三態 ＋ 三個結構性旗標並存**（本節最重要的產出）
```
# spec ∈ shared/macro_buckets.py:BUCKET_DANGER_SPECS（實測 16 盞）
if   spec.wired is False:        ⬜「尚未接線」 不進分母 不計未評估   # 結構性旗標①
elif spec.emits_level is False:  值可讀但不出等級 不進分母 不計未評估  # 結構性旗標②（2026-08-26 user 裁示）
elif miss_reason is not None:    ⚪「未評估」  不進分母 計入未評估    # ← INDICATOR_SPEC 三態（缺漏／不適用）
elif not within_valid_range(v):  ⚪ + MISS_CONTRACT_DRIFT 不進分母 計入未評估
else: level = classify_danger(v) 🟢/🟡/🔴      進分母
      if spec.discriminative is False: 照常判燈、照常進分母，另掛 degraded_reason   # 結構性旗標③
```
⚠️ **三旗標不是三態的子類，不可互相替代**（`shared/station_specs.py` 明文，2026-08-26 user 裁示）：**三態問「這一輪有沒有值」**（可重試／等資料），**旗標問「這盞燈結構上會不會出等級」**。⛔ **不得**把 `emits_level=False` 併進 `MISS_NOT_APPLICABLE` —— 把 KD 標成「不適用」在畫面上是假話（裁示逐字理由），且會覆蓋一條已生效的 user 裁示。另 `REFERENCE_TREND_SPECS`（`usdtwd`／`taiex`）有門檻但明文不進 16 盞分母、不進 worst-of，屬第四種「不參與」，同樣不與三態混用。
**R1-2 加權**：16 盞燈**不加權**（worst-of）；唯一權重在 `health` 內部 `health = Σ(vᵢ·wᵢ) ÷ Σwᵢ`，`i ∈ 有值腿`，`HEALTH_WEIGHT_JQ=0.6`／`HEALTH_WEIGHT_SCORE=0.4`（`shared/signal_thresholds.py` SSOT）。單腿缺 → 同時退出分子分母 ＋ `health_partial=True`；**兩腿全缺 → `health=None`**（⛔ 不是 0 分）→ 交 R6-1 分支 0。
**R1-3 投票：五套合成法並存，各有各的分母（⛔ 不得互餵）**

| 合成法 | 用在哪 | 分母 | 規則（檔:符號） |
|---|---|---|---|
| 桶內 worst-of | 五桶各自的燈 | **無分母**（`gray` 不在 `LEVEL_RANK`，不 rescale） | `red>yellow>green`；同色取 `danger_exceedance` 最大者為主因 — `macro_buckets.py:aggregate_level` |
| 全站危險度 | 總經頁抬頭 | 同上 | 五桶再 worst-of 一次；明文**不得**生第三顆合併燈 — `tab_macro_v2.py:overall_verdict` |
| 拐點分群投票 | 拐點面板 | **唯一有分母者** `n_evaluable=n_bull+n_bear+n_neutral` | 群內取最壞不累加，再比群數；`<PIVOT_MIN_EVALUABLE_FAMILIES(2)` → `insufficient` — `macro_helpers.py:aggregate_pivot_families` |
| 曝險分數 | 系統狀態 | base 60 ± delta，clamp `[0,100]` | 3 條硬否決取 min；`≥70`／`≥40`／`<40` 三級 — `macro_state_locker.py:calculate_system_state` |
| 出場三維 | 個股出場 | 命中計數 0~3 | 查表（`D-12`） — `exit_signals.py:evaluate_exit_signals` |

| 輸入 | 預期輸出 |
|---|---|
| `foreign_net`（`wired=False`）＋ 另 15 盞全綠 | 🟢；未評估計數 **+0**，印「尚未接線」（**缺值案例**；⛔ 不得計為缺漏、⛔ 不得判紅） |
| 16 盞**全部**為 `None`（未載入） | 全站 ⚪「未評估」（**邊界案例**；⛔ 不得回 🟢） |
| `margin`（`discriminative=False`）超標 | 照常 🔴 ＋ 掛 `degraded_reason`（⛔ 不得因不具鑑別度就移出分母）；1 盞紅 15 盞綠 → 🔴（worst-of，不稀釋） |

**應然 vs 實然**：三旗標 ＋ 五種缺因側車**已是最佳樣板，維持（相同）**；`macro_state_locker.calculate_system_state._f` 以中性值（VIX=20／PMI=50／PCR=1.0）表達缺值且無 partial 旗標 → **實作 bug**（`P1-01`／`D-06` 同族）。
## §2 個股健康度六因子
**R2-1 評分表**（分支順序即判定順序）— `src/compute/scoring/scoring_helpers.py:calc_health_score`

| 因子(滿分) | 條件 → 得分（括號＝SSOT 常數） |
|---|---|
| 趨勢 30 | `P>MA20>MA100`→30 ｜ `P>MA20 且 P>MA100`→18 ｜ `P>MA20 且 P<MA100`→10 ｜ `P<MA20 且 P>MA100`→8 ｜ 其餘→0 ｜ **MA 任一缺/為 0→15**（`D-28`） |
| RSI 20 | `50≤r≤70`→20 ｜ `40≤r<50`→12 ｜ `30≤r<40`→8 ｜ `r<30`→**14** ｜ `r>70`→8（`RSI_STRONG_LOW=50`/`RSI_OVERBOUGHT=70`/`RSI_NEUTRAL_WEAK_LOW=40`/`RSI_OVERSOLD=30`） |
| 量比 15 | `vr>3.0`→**12** ｜ `1.5≤vr≤3.0`→15 ｜ `1.0≤vr<1.5`→10 ｜ `0.5≤vr<1.0`→5 ｜ `vr<0.5`→2（`VOLUME_RATIO_SURGE_HIGH/SURGE/MILD/DRY`） |
| KD 15 | `k>d 且 k<80`→15 ｜ `k>d 且 k≥80`＋頂背離→5／高檔鈍化→15／其餘→8 ｜ `k<d 且 k>20`→5 ｜ 其餘＋底背離→13／無旗標→10（`KD_OVERBOUGHT_LEVEL=80`/`KD_OVERSOLD_LEVEL=20`） |
| IBS 10 | `ibs≤0.2`→10 ｜ `ibs≥0.8`→2 ｜ 其餘→6（`IBS_OVERSOLD/OVERBOUGHT_THRESHOLD`） |
| 布林 10 | `near_upper`→8 ｜ `P>MA`→6 ｜ `bw<bw_mean×0.7`→9 ｜ 其餘→3（`BB_BW_SHRINK_WARN_RATIO`） |

**R2-2 缺值與級距**
```
有值因子個數 = |{f : (值, None)}|                        # 「不適用」與「缺漏」都不算有值
if 有值因子個數 <= 6 × SCREENER_MIN_FACTOR_COVERAGE_RATIO:    # 嚴格 > 才通過 ⇒ 6 因子需 ≥4 個有值
     return None, most_fundamental_miss([...])           # 不出分、不出等第，走 INDICATOR_SPEC R-3 缺漏
else: return round(Σ得分ᵢ ÷ Σ滿分ᵢ × 100, 1), None  (+ partial=True, missing=[...])
# 等第（現行 code 字串常數；shared/health_thresholds.py + scoring_helpers.py:health_grade）：≥HEALTH_GRADE_A_MIN(80)
#   → A 🟢「優質優良」｜ ≥HEALTH_GRADE_B_MIN(50) → B 🟡「震盪盤整」｜ 其餘 → C 🔴「弱勢危險」
# ⛔ 缺漏不得落到 C；C 與「⚪ 未評估」不得同形（INDICATOR_SPEC R-3）
```
| 輸入 | 預期輸出 |
|---|---|
| 六因子全為 `None` | `(None, MISS_NO_INPUT)` → ⚪ 未評估（**缺值案例**；⛔ 不得 `0` 分 → C，`D-01`／`P1-03`／`N-2`） |
| 恰好 3 個有值（`3 > 6×0.5` = False） | 不出分 → ⚪ 未評估（**邊界案例**；⛔ 不得因分母變小而出高分，`A2-2`／`A2-6`） |
| 4 個有值、Σ滿分 75、Σ得分 60 | `80.0`、`partial=True`、`missing=[…]`，等第旁**必須**標 partial；MA20／MA100 皆缺時趨勢判**缺漏**（不進分子分母）→ 剩 5 因子 rescale，⛔ 不得 `+15/30`（`D-28`） |

**應然 vs 實然**：權重 30/20/15/15/10/10 為函式體內 inline literal（非 SSOT）＋ `MA 缺 → +15/30` 是全函式唯一憑空給值分支且被測試釘死 → **實作 bug**（`D-28`）；RSI／量比兩處非單調 → **刻意設計，非 bug**（`D-29`，user 2026-09-16 裁示選（甲））；健康分數現遭 7 處跨股票排名／篩選，與同日新增之排名禁令不符 → **設計變更**（`D-35`）。
## §3 估值評價：357 ＋ EPS≤0
**R3-1 357 ＝ 殖利率 7%／5%／3%**（`shared/thresholds.py:classify_stock_357_price`）｜**R3-2 EPS 三分流（虧損 ≠ 無資料）**
```
cheap 便宜價 = avg_div ÷ YIELD_HIGH_DEC(0.07)｜fair 合理價 = avg_div ÷ YIELD_MID_DEC(0.05)｜dear 昂貴價 = avg_div ÷ YIELD_LOW_DEC(0.03)
# 皆 round(x,1)；avg_div 量綱＝元/股（5 年平均現金股利）。KPI 卡標籤為現行 code 字串常數：'現價'／'🟢便宜(7%)'／'🟡合理(5%)'／'🔴昂貴(3%)'
if price<=0 or avg_div<=0: return 'na', {}   # → 三態的「不適用」，⛔ 不得判成昂貴
elif price<=cheap:'cheap' elif price<=fair:'fair' elif price<=dear:'dear' else:'overpriced'
# ── R3-2 ──
if   TTM EPS 序列為空 / 全 NaN: return None, MISS_NO_INPUT      → '⚠︎ —' ＋「上游這輪失敗，可以重跑一次」
elif 有效季數 < 4:              return None, MISS_NOT_ENOUGH     → '⚠︎ —' ＋「等時間累積（重跑無用）」
elif TTM EPS <= 0:             return None, MISS_NOT_APPLICABLE  → 'N/A'（**真虧損**）＋ 引導看 P/B 河流圖
else:                          畫 PE 河流圖
# ⛔ 前三條不得共用同一句文案；⛔ 無資料不得被渲染成「虧損」
```
| 輸入 | 預期輸出 |
|---|---|
| TTM EPS 全無資料 | `(None, MISS_NO_INPUT)`（**缺值案例**；⛔ 不得顯示「TTM EPS = 0.00 元（虧損）」，`D-30`） |
| `price` 恰等於 `cheap` | `'cheap'`（`<=` 含邊界，**邊界案例**） |
| TTM EPS `= -1.20`（真虧損） | 不適用 ＋ 引導看 P/B（現行行為正確，維持）；`avg_div=2.0`／`price=20` → `cheap=28.6`、`'cheap'` |

**應然 vs 實然**：`section_357_valuation.py:_render_pe_river` 的 `_cur_eps_pe = … else 0` 使「無資料」與「真虧損」同路同文案 → **實作 bug**（`D-30`）；PE 分帶無 SSOT、不分產業 → `D-13`／`D-14`。
## §4 組合風險：系統拿什麼數字去比、比完顯示什麼
> **本節定義的是「系統拿什麼數字去比、比完顯示什麼」，⛔ 不是「使用者該持有多少」。⛔ 不發明任何新門檻。缺項填補測試（全檔適用）**：從觀察走到行動，若需要代入只有讀者才有的變數（資金／期間／風險承受度／既有部位）而文字替他填了 → 那是投資建議，本檔**不寫**。

| 量測項 | 系統拿去比的數字 | **誰決定的**（強制欄） | 比完顯示 |
|---|---|---|---|
| 單一持股權重（個股組合） | `0.10`（**比例 0–1，非 %**；顯示端自乘 100，`D-25`） | **寫死** `src/config/config.py:MAX_POSITION_PER_STOCK`，無 UI 可改 | 現行 code 字串常數 `🔴 單股超過 10%:…`／`🟢 最大單股 X%(上限 10%)`／`🟢 集中度 OK` |
| 持股檔數（個股組合） | `10` | **寫死** `config.py:MAX_POSITIONS` | 同上 |
| 產業集中度（**個股**組合） | 有效產業數 `1/HHI`、最大產業佔比、前三大合計 | **刻意無門檻** — `src/compute/risk/concentration.py` 明文「本模組不提供任何燈號 / 門檻」（**user 2026-08-14 裁示**） | 三個 `st.metric` ＋ 分佈長條，**無燈號** |
| 產業上限（**ETF** 組合） | `30`（%） | **寫死**，inline L4 私有常數 `src/ui/render/etf_render.py:_SECTOR_CONCENTRATION_MAX_PCT` | `⚠️ 超限`／`✅`／`⚪ 無法判定`（未對映類股歸「其他」，不判超限） |
| 相關性（**個股**組合） | — | **查無**（無實作） | — |
| 相關性（ETF 矩陣） | `0.85` | **寫死** SSOT `shared/signal_thresholds.py:ETF_CORR_HIGH_THRESHOLD` | 逐對 `st.warning`／`st.error` |
| 相關性（ETF 分散度 平時／崩盤日） | `0.7`／`0.7`（崩盤日取最差 `DOWNSIDE_QUANTILE=0.20` 交易日） | **寫死**，inline `src/compute/etf/etf_smart_analysis.py:PRICE_CORR_HIGH_WARN`／`DOWNSIDE_CORR_HIGH_WARN` | 表格加「價格警示／空頭警示」欄 |
| 風險佔比 − 市值佔比 | `10.0`（百分點） | **寫死** SSOT `shared/risk_contribution_thresholds.py:RC_CONCENTRATION_GAP_PCT` | 集中警示 |

**R4-1 判定順序（先判能不能算，再判有沒有門檻）**
```
if   n_classified == 0:        is_computable=False，顯示診斷；⛔ 不得以 hhi=0／0% 頂替
elif n_classified < n_total:   只對已分類部分計算，**強制同時顯示 coverage_pct**；⛔ 不得靜默縮分母
if 帳本無張數:                 basis='equal_weight'，UI **強制揭露等權假設**；⛔ 不得把等權結果講成實際權重
if 該量測項有門檻:              比對後顯示「狀態 ＋ 門檻數值 ＋ 誰決定的」三件
else:                          **只印量測值**；⛔ 不得補門檻、⛔ 不得把量測值講成「過高／應降低」
```
✅ **已決事項｜個股組合刻意不設門檻，只量測、不出燈號** —— **`user 2026-09-16 拍板：維持 user 2026-08-14 裁示，⛔ 不得自行推翻`**。日後若要加門檻，該門檻必須是「使用者可設定參數」而非系統寫死，且須 user 另行明文推翻 2026-08-14 裁示（⛔ 不得由本檔或任何實作端逕自補上）。

| 輸入 | 預期輸出 |
|---|---|
| 8 檔全部查無產業別 | `is_computable=False` ＋ 診斷（**缺值案例**；⛔ 不得回 `HHI=0`／「集中度良好」）；10 檔中 3 檔查無 → 對 7 檔算 ＋ `coverage_pct=70.0` 同畫面揭露 |
| 最大單股恰為 `10.0%` | **不超標**（`>` 才紅，**邊界案例**）→ `🟢 最大單股 10.0%(上限 10%)` |
| 12 檔、最大單股 14% | `🔴 單股超過 10%` ＋ 同時顯示門檻 `10%` 與「系統寫死」（⛔ 不得寫「應減碼至 10% 以下」）；個股組合最大產業佔比 65% → 只印 `65%` ＋ 有效產業數，**無燈號、無門檻**（依 2026-08-14 裁示） |

**應然 vs 實然**：`basis='equal_weight'` ＋ `coverage_pct` ＋ `is_computable` 三件**已落地的誠實揭露，規格保住、不得取消（相同）**；常數名未編碼單位 → `D-25`；ETF 產業 30%／相關性兩個 `0.7` 為 inline → **實作 bug**（`D-31`）。
## §5 配置偏離：三套「目標」並存
| # | 目標從哪來（檔:符號） | 目標值 | 容忍帶 | **誰決定容忍帶** |
|---|---|---|---|---|
| (a) | 固定核心/衛星 — `src/services/dividend_station_service.py:compute_allocation_split` | `CORE_TARGET_PCT=80.0`／`SATELLITE_TARGET_PCT=20.0`（`shared/dividend_station_thresholds.py`） | **查無** —— 卡片僅 inline `abs(dev)>=1`（1 百分點）決定短標籤 | **寫死**（inline，`src/ui/views/page_hold.py:build_allocation_split_card`） |
| (b) | 依 regime 浮動 — `src/compute/strategy/portfolio_manager.py:_CORE_RATIO` | `bull .60 / neutral .70 / caution .80 / bear .85` | **±10 百分點（雙邊）** `PORTFOLIO_CORE_SAT_TOLERANCE_PP=10.0` | **寫死** SSOT，使用者不可改 |
| (c) | 逐檔目標 vs 實際 — `src/compute/etf/portfolio_gates.py:evaluate_rebalance_gate` | 使用者當場在 `st.data_editor` 逐檔輸入（欄 `目標比例%`），**不持久化** | **使用者可設定** `st.slider('再平衡容忍偏離度（%）', 1, 15, 預設 5)`；預設 SSOT `PORTFOLIO_REBAL_TOLERANCE_DEFAULT_PCT=5.0`；總和容差 `PORTFOLIO_TARGET_SUM_TOLERANCE_PP=1.0`（寫死） | **使用者**（全 repo 唯一，見檔尾待驗 3） |

⚠️ (a)(b) 是**兩把尺**，repo 已明文「只揭露不改」（`src/ui/render/station_cards.py`）→ **保住並存**，⛔ 不得合併、⛔ 不得以 (b) 頂替 (a)。**帳本沒有目標比例欄**：`portfolios` 分頁 header 只有 `['name','ticker','lots','avg_price','updated_at']`（`src/data/portfolio/gsheet_portfolio.py:_HEADERS`）。
```
if 目標留白／部分留白／總和偏離 100% 超過 PORTFOLIO_TARGET_SUM_TOLERANCE_PP:
     'unknown' ⚪「無法判定」；⛔ 不得拿現況當目標、⛔ 不得補 0、⛔ 不得判綠燈
elif regime is None (b 路徑):  'unknown'；⛔ 不得預設 0.70
elif 全區間在容忍帶內:'pass' elif 全區間在帶外:'fail' else:'unknown'（跨邊界／未分類部位會左右結論）
# 顯示：目標% / 實際% / 偏離度% 三欄，未設定一律印 '—' ＋ caption「系統不會拿現況當目標」
```
| 輸入 | 預期輸出 |
|---|---|
| (c) 5 檔全部留白 | `'unknown'` ⚪ 無法判定 ＋ 三欄印 `—`（**缺值案例**；⛔ 不得判 pass）；全組合無市值 → (a) 回 `None`，⛔ 不得用檔數頂替比例 |
| (b) `dev=+10.0pp`、`tol=10.0pp` | 帶內 → `pass`、`delta_color='normal'`（`<=` 含邊界，**邊界案例**） |
| (c) 目標總和 `=98.5%`（容差 1.0pp） | 超出容差 → `'unknown'`；⛔ 不得自動正規化到 100% |

**應然 vs 實然**：三套目標刻意並存且已揭露 → **相同（維持）**；(a) 無容忍帶、只有 inline `1` → **實作 bug**（`D-31`）；帳本無目標比例欄、(c) 不持久化 → **設計變更**（要讓使用者填＝新增畫面元件，須先過 `CLAUDE.md §-1.5` UI 草稿先行 gate）。
## §6 衝突解決矩陣
| 衝突 | 誰贏 | 依據（檔:符號） |
|---|---|---|
| 總經 vs 個股技術面 | **總經**（惡化凌駕技術面多頭） | `shared/regime_arbiter.py:arbitrate_regime`；`CLAUDE.md §2.1`「上層贏、禁止平均」 |
| 總經「危險度」vs「多空位階」 | **都不贏 —— 刻意並存、並列揭露** | `tab_macro_v2.py:DANGER_TITLE`／`DIVERGENCE_NOTE`（實跑 400 組燈色不一致 39.5%，**客戶核准刻意不調和**；⛔ 不得當 bug 修、⛔ 不得生第三顆合併燈） |
| 組合上限 vs 個股評分 | **組合上限**（風險閘門先於選股結論） | `src/compute/risk/risk_control.py:check_portfolio_limits` 是 gate、非評分項 |
| 配置偏離 (a) vs (b) | **都不贏 —— 兩把尺並列** | `src/ui/render/station_cards.py`「兩把尺，只揭露不改」 |
| 同一指標兩套判燈門檻 | **應只有一套**（`D-32`） | `CLAUDE.md §2.1` SSOT；現況違反 |

**R6-1 大盤 regime 唯一仲裁點，先命中先贏** — `shared/regime_arbiter.py:arbitrate_regime`
```
if   not is_loaded or health is None/NaN:       ⬜ unknown  (source='unloaded')  # ⛔ 絕不退回 'neutral'
elif is_foreign_futures_defense(score, fut):    🔴 bear     (defense:foreign_futures)
     # score < DEFENSE_MAX_MARKET_SCORE(2) ∧ fut < 0 ∧ |fut| > FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD(30000)
elif health < HEALTH_DEFENSE_THRESHOLD:         🔴 bear     (defense:health_below_threshold)
elif trend=='bull' and score >= BULL_MIN_SCORE: 🟢 bull     (bull:score)
elif trend in ('caution','bear'):               🔴 bear     (bear:trend_regime)
else:                                           🟡 neutral  (neutral:fallthrough)
# ⛔ 禁止由 icon 反推 regime；三欄位契約 regime(輸入)／effective_regime(結論)／light+regime_source 不得互換
```
⚠️ **同一批指標有兩套門檻、兩套都有 production caller**：`src/config/config.py:MACRO_ALERT_RULES`（VIX 30/20、CPI 3.5/2.5、US10Y 4.8/4.2、DXY 107/103；caller ＝ `src/data/macro/macro_alert.py:check_macro_alerts`、`src/services/ai_structured_summary.py`）vs 五桶 `BUCKET_DANGER_SPECS`（VIX 30/22、CPI 4.0/3.5、US10Y 5.0/4.5、DXY 110/105）。**應然：同一指標只能有一套判燈門檻** → **`D-32`（新編號）**。

| 輸入 | 預期輸出 |
|---|---|
| `is_loaded=True`、`health=None` | ⬜ unknown（**缺值案例**；⛔ 絕不退回 `'neutral'`、⛔ 不得以 `health=0` 觸發紅燈） |
| `health=35.0` 恰等於門檻 | **不觸發** defense（`<` 才成立，**邊界案例**）→ 續判分支 3 |
| `health=30`、`trend='bull'`、`score=6` | 🔴 bear（分支 2 先命中，**總經贏技術面**）；VIX `=21` → 五桶 🟡 但 `MACRO_ALERT_RULES` 🟢（`D-32`） |

**應然 vs 實然**：仲裁樹集中於唯一函式 → **相同（維持）**；危險度 vs 位階分歧 → **刻意並存（設計，非 bug）**；兩套門檻 → **實作 bug**（`D-32`）。
## §7 時間軸：訊號「剛出現」vs「持續中」
**現況**：全站**沒有任何一盞燈帶「已紅 N 天」** —— `DangerSpec`／`RegimeVerdict`／五桶側車 `_rec()` 的 9 欄**一個時間欄都沒有**。既有跨期比較只有 5 處且都在**取數層**、進合成端只被當成當期布林訊號：外資連續日數（`tw_macro.py:fetch_foreign_consecutive_days`）、NDC 連 2/3 月（`fetch_ndc_signal_history`）、領先指標 6M 轉正（`fetch_ndc_leading_index`）、均線 3 日遲滯（`market_strategy.py:market_regime`）、值凍結偵測（`shared/data_freshness.py:detect_frozen_columns`）。**R7-1 最小可行時間軸契約** —— 一盞燈要帶什麼欄才能講「剛翻紅」vs「紅了三週」：
```
# 既有輸出加 4 欄（schema-additive，既有 caller 無感）；歷史源＝已落地但目前無消費端的
# data_cache/macro_forward_test/signals.parquet（schema shared/macro_forward_test_schema.py，含 ruleset_hash）
prev_level:str|None 上一期燈色，無歷史→None（⛔ 不得預設 'green'）｜ since:date|None 首次進入 current_level 的日期
streak:int|None 已維持期數（含本期），無歷史→None（⛔ 不得 0 —— 0 與「剛翻第 1 期」不可分）｜ streak_miss:str|None 沿用三態
if   prev_level is None:            只印當期燈色；⛔ 不得印「剛翻紅」也不得印「持續」
elif current_level != prev_level:   轉折 → streak=1、since=本期
elif ruleset_hash 與前期不同:        streak 中斷重算；⛔ 不得跨規則版本累計
else:                               持續 → streak += 1
# ⛔「持續 N 期」的 N 必須是具名常數；⛔ 不得在文案寫死一個實作沒做的期數
```
| 輸入 | 預期輸出 |
|---|---|
| 首次啟用、無 parquet 歷史 | `streak=None` ＋ `streak_miss=MISS_NOT_ENOUGH` → 只印燈色（**缺值案例**；⛔ 不得印 `streak=0`） |
| 連 3 期 🔴，但第 2 期 `ruleset_hash` 變了 | `streak` 自第 2 期重算 = 2（**邊界案例**；⛔ 不得宣稱 3 期） |
| 昨 🟡、今 🔴 | `prev_level='yellow'`、`streak=1`、`since=今日` → 「剛轉紅」；值凍結（連 3 期差分 0）→ 降級未取得，`streak` 不遞增 |

**應然 vs 實然**：燈號無任何時間欄、歷史 parquet 已落地卻無消費端 → **設計變更**（`D-33`）；`data_registry.py:FRED_NAPM['how_to_read']` 印「`< PMI_RED 持續 3 月` → 🚨 衰退強烈訊號」但全站**沒有** PMI 連 3 月的檢查（只有連 2 月的 `MACRO_VETO_PMI_CONTRACTION_LEVEL`）→ **實作 bug**（`D-34`），修法二選一（補實作／改文案），⛔ 不得維持現狀。
## §8 新編號（接續 `INDICATOR_SPEC §5` 的 `D-27`）
| 編號 | 一句話（**應然**） | 檔案:符號 | 分類 |
|---|---|---|---|
| D-28 | 六因子權重應下沉 `shared/` 成可讀資料結構；MA 缺應回缺漏，⛔ 禁 `+15/30` 憑空給值 | `src/compute/scoring/scoring_helpers.py:calc_health_score` | 實作 bug |
| D-29 | **`user 2026-09-16 裁示：選（甲）刻意`**。(a) RSI<30→14、量比>3.0→12 兩處**非單調是刻意的**，各代表「超賣反彈機會」「異常放量」，⛔ 不得當 bug 修、⛔ 不得改回單調；(b) 同日**新增限制：健康分數禁止用於跨股票排名，只能跟自己的歷史比** —— 分數是多訊號加總，跨股票比大小無意義（既有違反見 `D-35`） | 同上 | **設計變更（user 2026-09-16 裁示）** |
| D-30 | TTM EPS 無資料應回 `(None, MISS_NO_INPUT)`，⛔ 禁 `else 0` 使其顯示為「虧損」 | `src/ui/tabs/stock_sections/section_357_valuation.py:_render_pe_river` | 實作 bug |
| D-31 | 組合端 inline 門檻應下沉 `shared/`（ETF 產業 30%、相關性 `0.7`×2、配置偏離 `abs(dev)>=1`）。⚠️ 射程**僅限既有門檻搬家**：**`user 2026-09-16 拍板：維持 user 2026-08-14 裁示，⛔ 不得自行推翻`** —— **個股**組合維持無門檻，⛔ 不得藉本條順手補上產業／相關性上限（見 §4 已決事項） | `etf_render.py:_SECTOR_CONCENTRATION_MAX_PCT`；`etf_smart_analysis.py:PRICE_CORR_HIGH_WARN`／`DOWNSIDE_CORR_HIGH_WARN`；`page_hold.py:build_allocation_split_card` | 實作 bug |
| D-32 | 同一指標只能有一套判燈門檻；現 VIX/CPI/US10Y/DXY 各兩套且都有 caller | `src/config/config.py:MACRO_ALERT_RULES` vs `shared/macro_buckets.py:BUCKET_DANGER_SPECS` | 實作 bug |
| D-33 | 燈號應帶 `prev_level`／`since`／`streak`／`streak_miss` 四欄（R7-1），歷史源用既有 parquet | `shared/macro_buckets.py:DangerSpec`；`shared/regime_arbiter.py:RegimeVerdict` | 設計變更 |
| D-34 | 教學字串宣告的「持續 3 月」與實作不符，須二選一對齊 | `src/data/core/data_registry.py:FRED_NAPM['how_to_read']` | 實作 bug |
| D-35 | `D-29`(b) 排名禁令在**下裁示前已存在 7 處違反**（⛔ 非 bug、⛔ 不得寫成 bug —— 是規則變了，這些寫法在 2026-09-16 前不算錯），全部在「🏆 個股組合」批次管線，產生端唯一 `run_batch_fetch`（寫 `健康度`／`評級`／`_health` 進 `session_state['t3_data']`；其 except／空 df 分支塞 `健康度: 0` 佔位＝`P1-03`／`N-2`，該 0 會被下列②當「體質弱」）：①`sort_values('健康度', ascending=False)` 直接排序（`_render_elimination_detail`）②`健康度 < HEALTH_GRADE_B_MIN(50)` 汰弱成 `eliminated_ids`（`summarize_candidates`）③多股表 `健康度`／`評級` 為可排序欄（`_render_master_table`）④等第加權進第一排序鍵 `_p`（`final_recommendation`）⑤多因子分缺席時改由 `_health` 決定名次再餵 LLM（`_ranked_t3`）⑥等第跨軸融合成「🧭統一裁決」可排序欄（`_render_summary_table`）⑦A 級 gate 進「操作狀態」欄（`classify_stock_status_lamp`）。**合規替代路徑已存在、即裁示允許的比法**：`scripts/update_health_history.py`(cron) → `health_history_service.py:HEALTH_HISTORY_PARQUET` → `load_health_history`／`merge_score_history` → `section_kline_chart.py`「📈 健康度走勢（近5日）」＝**單檔跟自己歷史比**。⚠️ **但該路徑至今零資料**（總管實查）：`health_watchlist.json` 的 `stocks` 為 `[]`（檔內自陳「清單為空 ＝ 功能待命不跑（不會腦補您的持股）」）、`health_history.parquet` 從未被 commit、workflow 自陳上線起跑 **33 次全成功但從未 commit 任何東西** → **7 處跨股排名禁掉後，健康分數剩下的唯一合規用途目前無資料可比**。**啟用條件＝把股票代碼填進該 json 的 `stocks` 並 commit，那是使用者的持股決定，⛔ 系統／本檔／任何實作端不得代填** | `src/ui/tabs/stock_grp_sections/section_batch_fetcher.py:run_batch_fetch`；`section_portfolio_summary.py:_render_elimination_detail`／`_render_master_table`；`src/compute/screener/scorability.py:summarize_candidates`；`src/ui/tabs/tab_helpers.py:final_recommendation`／`classify_stock_status_lamp`；`section_ai_portfolio.py:render_ai_portfolio_section`(`_ranked_t3`)；`section_financial_health.py:_render_summary_table`；啟用側 `data_cache/health_watchlist.json`（`stocks`）／`.github/workflows/update_health_history.yml` | **設計變更（user 2026-09-16 裁示）** |
## §9 客戶裁示：六項策略衝突（`user 2026-09-21` 逐字拍板）
> 六項衝突原文見 `STRATEGY_INTAKE.md §2`（同批另立；⛔ 本節只收**裁示 ＋ 可照著實作的判定邏輯**，不轉述該檔）。裁示逐字以 **粗體引號** 標明；沿用全檔三態與語氣（免責見檔首，⛔ 不重述），⛔ 不動 §1~§8 任何既有規則、⛔ 不另立 `D-*` 編號（§8 表不動）。
**R9-1（C1 同一時點三套方法論給相反位階，誰優先）** — **「分層並列，不互相否決。真衝突時總經贏。」** 接 §6 衝突矩陣既有體例（⛔ 既有五列一字不動）：總經配置／財報五大數字選股／週期循環定位**三層各出各的結論、同畫面並列揭露**；只有「同一個欄位只能印一個值」才算**真衝突**，此時取總經 — 與既有「總經 vs 個股技術面 → 總經贏」同向，⛔ 不得反推成「總經可覆寫另兩層的欄位」。
```
# layer ∈ {macro 總經配置, fundamental 財報選股, cycle 週期定位}；每個輸出強制帶 layer 欄
if   三層各有自己的欄位:        三層全印 ＋ 各標 layer 與時間尺度(R9-2)；⛔ 不得以一層否決另一層、⛔ 不得只印贏的那層
elif 同一欄位被多層爭用:        # ← 只有這一格叫「真衝突」
     if macro 有值(非三態缺):   該欄取 macro；另兩層結論**原樣並列**同畫面；⛔ 不得隱藏、⛔ 不得生第三顆合併燈
     else:                      ⚪「未評估」；⛔ 不得由 fundamental／cycle 遞補頂替總經欄位
```
**R9-2（C2 時間尺度不一致：財報落後季頻、週期領先月頻）** — **「不合成，各自標時間尺度。」**

| 層 | 指標性質 | 頻率 | 可用日（PIT 對齊鍵，`CLAUDE.md §2.3`） |
|---|---|---|---|
| macro 總經配置 | **逐源標註**，⛔ 不得以單一性質概括 | 逐盞不同（16 盞各有來源） | 依各源發布延遲逐項標 |
| fundamental 財報選股 | **落後** | **季頻** | **公告日（約季後 45 天）**；⛔ 不得用季末日 |
| cycle 週期定位 | **領先** | **月頻** | 公告日 |

每個輸出**必須**帶 `scale` 三件（頻率 ＋ 落後/同時/領先 ＋ 可用日）；⛔ 不得把不同尺度的結論合成一個數字或一盞燈（同 §1 R1-3「五套合成法各有各的分母、⛔ 不得互餵」）；⛔ 不得拿季頻值去填月頻空格（那是沉默 `ffill`，違 `CLAUDE.md §1`）。
**R9-3（C3 輸出型別不同：整體曝險 % vs 個股百分位排名）** — **「不相加，不同層級。」**
```
# exposure_pct 單位 %（組合層）｜ percentile 單位 pctile（個股層）— 值域同為 [0,100]，但**語意與層級不同**
if   兩值來自不同層級:        分欄顯示，各標單位 ＋ 層級；⛔ 不得相加／相乘／平均／併進同一排序鍵
                              ⛔ 不得因「都是 0~100」就當同量綱（`CLAUDE.md §4.1` 量綱陷阱）
elif 畫面只容得下一個數字:    ⚪「不合併」＋ 兩值並列；⛔ 不得自造轉換係數把百分位換算成曝險 %
```
**R9-4（C4 週期定位核心輸入本機無資料源）** — **「標『本機缺資料，暫不啟用』。」** 射程＝該層核心輸入（殖利率利差 10Y-2Y／10Y-3M、Fed 資產負債表 WALCL）；依 `STRATEGY_INTAKE.md §2` C4 查證：全 repo 僅教學字串命中、無任何 fetch。⛔ 不得為此新增資料源、⛔ 不得以中性值／0 頂替（`P1-01`／`D-06` 同族）。
```
if   該輸入全 repo 無 fetch 實作:  顯示**「本機缺資料，暫不啟用」**；不進分母、不計未評估
                                   # ＝ §1 R1-1 結構性旗標①「尚未接線」那一格；⛔ 不得改掛三態「缺漏」（重跑無效）
elif 有 fetcher 但這輪沒取到:      三態「缺漏」`⚠︎ —`（可重跑）
else:                              照常判
# ⛔ 整層停用不得使該層判綠；該層在 R9-1 爭用時視同「無值」，走 else 分支
```
**R9-5（C5 同一指標雙軌門檻：VIX）** — **「統一成一套門檻，或明確分工（22 警戒 / 25-30 恐慌分級），寫清楚。」** **總管裁定：選「分工」，不統一**（⛔ 非客戶原文，`CLAUDE.md §-2` 規則 6，客戶一句話即可推翻）。理由：兩軌**目的不同**；強行統一＝改動兩個現行系統的行為，屬程式碼變更、超出本輪射程。

| 軌 | 門檻（檔:符號） | 值 | 管什麼 | 出現在哪 |
|---|---|---|---|---|
| **位階軌** | `shared/macro_buckets.py:DangerSpec("vix")` → `MACRO_THRESHOLDS['VIX']`；note 欄逐字 `≥22 警戒 / ≥30 流動性危機強制空手`（**現行 code 字串常數**，原樣引用） | `yellow_above=22`／`red_above=30` | **總經位階燈號**（五桶之一） | 五桶／總經頁抬頭（§1 R1-3） |
| **雷達軌** | `src/compute/risk/risk_radar.py:VIX_WARN_LEVEL`／`VIX_PANIC_LEVEL` | `25.0`／`30.0` | **事件雷達分級**（單一事件強度） | `src/ui/tabs/macro/helpers.py`（卡片 cut-off 線 ＋ `detect_risk_radar`）／`tab_macro.py` 風險雷達桶 |

```
# 位階軌燈號判定逐字（`src/data/macro/macro_core.py`）：>red_above(30) ⚫ 極端恐慌／>yellow_above(22) 🟡 波動加劇／其餘 🟢 市場平靜
if   畫面印的是「總經位階」:      只引位階軌 22/30；⛔ 不得混入 25
elif 畫面印的是「事件雷達強度」:  只引雷達軌 25/30；⛔ 不得混入 22
# ⛔ 同一個畫面不得同時引用兩軌 —— 同一天 VIX=23 會同時出現 🟡 與 🟢，兩盞燈互相打臉
```
⚠️ **射程僅限本對**（位階軌 vs 雷達軌）：§6／`D-32` 那一對（`MACRO_ALERT_RULES` VIX 30/20 vs `BUCKET_DANGER_SPECS` 30/22）**不在本裁示射程內，仍為實作 bug 待修**，⛔ 不得引本條把 `D-32` 講成「已裁示分工」。
**R9-6（C6 缺值語意在 repo 內不一致）** — **「全面統一為三態（有值 / 不適用 / 缺漏），違反側列為實作待修。」** 語彙 SSOT：`⚠︎ —` ＝**缺漏・可重跑**；`N/A` ＝**不適用・重跑無效**（`UI_COMPONENTS.md §2` 徽章 #7／#8）；⛔ 兩者不得同形（同 `INDICATOR_SPEC` R-3 ／ §2 R2-2）。 ✅ **已合規樣板（維持，⛔ 不得回頭改成 0）**：`fundamental_prescreen.py:_safe_ratio`（分母 ≤0 → `NaN` ＝**不適用**）／`yield_pe_fetcher.py:get_pb_ratio`（雙源皆敗 → `None` ＝**缺漏**）／`v5_modules.py:calc_dividend_yield_357`（缺 → `est_yield=None` ＋「未評估」，不出分）。

| 違反側（**只登記、本輪不修**） | 現行行為 | 應然（三態） |
|---|---|---|
| `C6-①` `tw_stock_data_fetcher.py:calc_financial_metrics` | 六個比率缺分母一律 `else 0.0` | 分母缺／≤0 → **不適用**；⛔ 禁 `0.0` |
| `C6-②` `financial_statements_fetcher.py:_v()` | 查無永遠回 `0.0` | 查無 → **缺漏**；⛔ 禁 `0.0` |
| `C6-③` `fuzzy_get_from_df(default=0.0)` | 查無回 `0.0` | 同上；⛔ 預設值不得為 `0.0` |
| `C6-④` `scoring_engine.py:calc_revenue_yoy_score` | 無資料回 `50.0` | 無資料 → **缺漏**、不出分；⛔ 禁中位分頂替 |

**應然 vs 實然**：C1／C2／C3 的並列與分尺度揭露，與五桶三旗標（§1）、兩把尺（§5）、「刻意並存」（§6）同一手法 → **規格保住（相同）**；C4 的「尚未接線」格已存在（R1-1 旗標①）→ **相同（維持）**；C5 雙軌並存 ＋ C6 四處 `0.0`／`50.0` 頂替 → **實作待修**（⛔ 本輪零程式碼變更）。
**出處與複驗**：C1~C6 裁示逐字為 `user 2026-09-21`；**C5 的「選分工不統一」是總管裁定、非客戶原文**（`CLAUDE.md §-2` 規則 6）。C5 兩軌常數值／燈號逐字／C6 兩側位置為**總管實查**；C5 表「出現在哪」一欄係本組讀 import 所得、**未實跑畫面**，亦**未查證兩軌現是否已同框**。⛔ 本節未窮舉其他雙軌門檻或其他缺值頂替點，⛔ 不得當「已全數收斂」的前提。
## 複驗狀態（`CLAUDE.md §-2` 規則 6）
- **✅ 總管親自查證，可當事實**：涵蓋門檻真實語意（因子個數 ＋ 嚴格 `>`）與 `INDICATOR_SPEC §4` 點數版不成立；`BUCKET_DANGER_SPECS` 實測 **16 盞**；`station_specs.py` 的 `emits_level` 為 2026-08-26 user 裁示且三旗標不可互相替代；`regime_arbiter.arbitrate_regime` 六分支存在；`concentration.py` 逐字「本模組不提供任何燈號 / 門檻」（2026-08-14 裁示）；`MAX_POSITION_PER_STOCK = 0.10`；`section_357_valuation.py` 的 `else 0`；`MACRO_ALERT_RULES` 兩套門檻並存且有真 caller。**`D-35` 之中 2 處為總管實查活碼**：`_render_elimination_detail` 的 `sort_values('健康度', ascending=False)`（檔內註解自陳「④ 汰弱留強改以『純健康度』排序」）、`summarize_candidates` 的 `health_min=HEALTH_GRADE_B_MIN` 汰弱；合規替代路徑三段 code（cron／service／K 線頁走勢圖）＋ 路徑常數 `HEALTH_HISTORY_PARQUET` 均實測存在，**但該路徑從未產生過資料**（四項皆總管實查，⛔ 非單組推測）：`health_watchlist.json` 受 git 追蹤但 `stocks: []`；`git log --all -- data_cache/health_history.parquet` 回空（從未 commit）；`update_health_history.yml` 檔內自陳跑 33 次全成功、0 commit（原因：parquet 被 `.gitignore` 蓋掉使無 `-f` 的 `add` 從未納管＋watchlist 空時 script 依設計 `exit 0`，現已改「存在才 `git add -f`」）；工作區無該 parquet。
- **⚠️ 單組調查結論（B1／B2／B3，未經第二組複驗，引用請打折）**：五套合成法「只有五套」；六因子給分規則逐分支還原與「唯一憑空給值分支是 MA」；時間軸機制「只有 5 處」且「無任何一盞燈帶時間欄」；三個上限「全部寫死」；`_SECTOR_CONCENTRATION_MAX_PCT` 等判定為 inline。**`D-35` 其餘 5 處 ＋「共 7 處、且全部集中在個股組合那條管線」** —— INV-1 單組窮舉（上列 2 處除外），未經第二組複驗；其中「多股表欄頭可點擊排序」係依 Streamlit 預設行為推導、**未實跑畫面驗證**，`_render_summary_table`／`classify_stock_status_lamp` 兩處屬「等第門檻進多股表」而非直接 `sort`，射程由本檔一併收錄。
- **⚠️ 本檔自己的全稱句（待驗，⛔ 不得當前提）**：1) 「§4 表列八項即個股與 ETF 組合的全部門檻」—— 依 B3 單組掃描，未自行窮舉。2) 「§6 矩陣五列即四層級間的全部衝突」—— 只覆核 B1 指出者，未窮舉跨層組合。3) 「再平衡容忍度是全 repo 唯一使用者可改的門檻」—— B3 單組（僅掃 `st.slider`／`st.number_input`），`st.session_state` 直寫路徑掃不到。4) 「`D-28`~`D-35` 未與 `D-01`~`D-27` 重複」—— 本組逐條比對，未經第二組驗。 5) **§7 R7-1 是本組自行設計，不是從 code 讀出來的** —— 四欄契約（`prev_level`／`since`／`streak`／`streak_miss`）與「`ruleset_hash` 變更即中斷 streak」**全站無既有實作可對照**，也未經第二組驗；且「歷史源用既有 parquet」係依 B1 轉述，本組**未實際讀取** `data_cache/macro_forward_test/signals.parquet`（欄位是否逐燈落地、資料密度是否足以回推 streak，**皆未驗**）。⛔ `D-33` 落地前必須先派一組獨立驗該 parquet 的 schema 與密度。
