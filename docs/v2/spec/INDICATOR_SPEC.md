# INDICATOR_SPEC — 指標「應然」規格（階段 B）

> **這是「應該是什麼」，不是「哪裡壞了」。** 症狀清單已在 `stage1/` 三份稽核裡；本檔定的是**根因**：
> 全站缺值的統一表達方式。根因定好，症狀自動被覆蓋。引用既有發現一律**只給編號**
> （`P1-01`~`P1-06` / `N-1`~`N-14`），不重述內容。
> **免責（全檔只講一次）**：本檔**不對任何標的產生買賣建議**，只定義指標如何計算與如何表達缺值。
> ⚠️ 單組產出，未經第二組獨立複驗（`CLAUDE.md §-2 規則 6`）。**⛔ 本輪零程式碼變更。**

## §1 根因：缺值的三態契約

全站**只有三種狀態**，載體是「**值 ＋ 並行的 `miss_reason`**」二元組（dict／dataclass 用 `miss_reason` 鍵；
DataFrame 用平行欄 `<欄名>_miss`）。`miss_reason` 取自既有 SSOT `shared/station_specs.py`（`MISS_NOT_APPLICABLE` /
`MISS_FETCH_FAILED` / `MISS_CONTRACT_DRIFT` / `MISS_NOT_ENOUGH` / `MISS_NO_VARIATION` / `MISS_NO_INPUT`
＋ `MISS_PRIORITY` / `most_fundamental_miss`），**不新增枚舉**。

| 狀態 | 意思 | L1 取數回 | L2 計算回 | 畫面顯示 |
|---|---|---|---|---|
| **有值** | 真的量到了（**含真的是 0**） | `(值, None)` | `(值, None)` | 數值（`0.00` 是正常值） |
| **不適用** | 這個標的結構上沒有這一項 | `(None, MISS_NOT_APPLICABLE)` | `(None, MISS_NOT_APPLICABLE)` | `N/A`（灰） |
| **缺漏** | 該有但沒拿到 | `(None, <MISS_* 其餘五者>)` | `(None, most_fundamental_miss(輸入缺因))` | `⚠︎ —` ＋ 該怎麼辦 |

### 三條禁令（各一句理由）

1. ⛔ **缺值不得用 `0` / `0.0` 表達** —— 它與「真的是 0」在型別上不可區分，而 0 在多數門檻裡是**一個有意義的結論**（最差那一級）。
2. ⛔ **缺值不得用 `''` / `'-'` / `'N/A'` 字串表達** —— 下游一律用 `in` 做子字串比對，空字串讓所有分支都不命中，**靜默退回預設分支**。
3. ⛔ **不得靜默** —— 缺值**必須帶 `miss_reason` 旗標**（不是例外、不是哨兵型別）。**為何選旗標**：取數一次處理多檔多欄，
   一欄缺就 `raise` 會把「一檔缺」放大成「整頁掛」；哨兵型別會讓既有 `is None` 檢查全數失效、算術錯誤在**遠離現場**才爆。
   旗標同時滿足 `CLAUDE.md §1`「顯式、寫 log、輸出帶旗標」三件事。

### 為什麼「不適用」與「缺漏」必須分開（本契約的關鍵）

| | 重試 | 分母 | 未評估警示 | 使用者該做什麼 |
|---|---|---|---|---|
| **不適用** | **無用**（結構性，重跑一百次一樣） | 從分母移除 | **不計入** | 不用做任何事，不是壞掉 |
| **缺漏** | **有用**（上游這輪失敗／等時間累積） | 從分母移除 | **計入** `本輪 N 項未評估` | 重跑，或等資料累積 |

混成一態 → 畫面只能給**一種**指引，而它對另一半使用者必然是錯的：叫他重跑一個永遠不會有值的東西，
或叫他等一個重跑就好的東西。⚠️ 兩者**都**不進分母，差別在**警示與指引**，不在算術。

## §2 套用規則：三條 if-else

### R-1 取數層（L1）：外部源沒給某欄時回什麼

```
if 結構上無此欄 (ETF 無 EPS / 金融股無毛利率 / 交易所 PE<=0 的虧損股): return None, MISS_NOT_APPLICABLE
elif 整批請求失敗 (HTTP / 解析 / token / fallback 鏈全敗):            return None, MISS_FETCH_FAILED
elif 有回應但欄名或型別不符契約:                                      return None, MISS_CONTRACT_DRIFT
elif 有資料但筆數 < 該計算所需最小窗:                                  return None, MISS_NOT_ENOUGH
elif 整段零波動 / 分母為 0:                                          return None, MISS_NO_VARIATION
elif 該筆輸入單獨沒拿到 (上游這輪沒給):                                return None, MISS_NO_INPUT
else:                                                               return 值, None   # 值可以是 0.0
```
⛔ 任一分支不得 `return 0` / `return ''` / `continue`（把該檔悄悄丟掉）/ `except: pass`。

| 輸入 | 預期輸出 |
|---|---|
| TWSE `PEratio` = `12.3` | `(12.3, None)` |
| TWSE `PEratio` ≤ 0（虧損股） | `(None, MISS_NOT_APPLICABLE)` —— ⛔ 不得與下一列同路（已知問題 #4） |
| TWSE `PEratio` 為 `NaN`／欄位不存在 | `(None, MISS_NO_INPUT)` |
| 日線僅 10 列、Sharpe 需 ≥20 列 | `(None, MISS_NOT_ENOUGH)` —— ⛔ 不得 `0.0`（`N-3`） |
| 連續 9 日 `high == low`（跌停鎖死） | `(None, MISS_NO_VARIATION)` —— ⛔ 不得把分母 0 換成 1 |
| 真實淨利率 `0.0`（邊界） | `(0.0, None)` —— **有值**，⛔ 不得顯示成缺值 |

### R-2 計算層（L2）：任一輸入是「缺漏」時，**不得往下算**

```
if 全部必要輸入皆 (值, None):                return 算出來的值, None
elif 本指標是「單一算式」(非加權評分):        return None, most_fundamental_miss([各輸入的 miss_reason])
else:                                      # 加權評分，見 §4
    缺漏 / 不適用的因子 → 分子與分母同時移除 (rescale)
    if 有效滿分 == 0 or 有效滿分 < 總滿分 * COVERAGE_RATIO:  return None, most_fundamental_miss([...])
    else:                                  return rescale 後的分, None  (+ partial=True, missing=[...])
```
⛔ 輸入不得用 `.get(k, 0)` / `or 0` / `or ''` 取值；⛔ 單一算式分支不得代入預設值續算；
⛔ `except` 不得回傳**部分結果**，一律 `(None, MISS_CONTRACT_DRIFT)` ＋ stderr log。
涵蓋門檻沿用既有 SSOT `shared/signal_thresholds.py:SCREENER_MIN_FACTOR_COVERAGE_RATIO = 0.5`（全站統一，不另立常數）。

| 輸入 | 預期輸出 |
|---|---|
| 個股健康 6 因子輸入全為 `None` | `(None, MISS_NO_INPUT)` —— ⛔ 不得 `0` 分 → 最差等第（`P1-03`／`N-2`） |
| 6 因子中 4 個有值（滿分 75）、2 個缺漏 | `(得分 ÷ 75 × 100, None)`、`partial=True`、`missing=['KD','布林']` |
| 6 因子中 1 個有值（滿分 30 < 100×0.5） | `(None, MISS_NO_INPUT)` —— 未過涵蓋門檻，不出分 |
| 日報酬全 0（`std == 0`，分母 0） | `(None, MISS_NO_VARIATION)` —— ⛔ 不得 `0.0`（`P1-04`） |
| 三個輸入全缺的市場狀態判定 | `(None, MISS_NO_INPUT)` —— ⛔ 不得回任何有方向的結論（`P1-01`） |

### R-3 呈現層（L4／L5）：收到三態各自畫什麼

```
if miss_reason is None:                  顯示 f'{value:.<n>f}'（含 '0.00'），正常色；⛔ 不得因為值是 0 就畫成灰
elif miss_reason == MISS_NOT_APPLICABLE: 顯示 'N/A'，灰；tooltip='這類標的沒有這一項'；⛔ 不計入「本輪 N 項未評估」
else:                                    顯示 '⚠︎ —'；tooltip=MISS_TEXT[miss_reason]；計入「本輪 N 項未評估」
```
⛔ **三態不得共用符號或顏色**：`⚪`／灰**一律只代表「不適用／未評估」**，「判過了、結論是中性」必須用具名標籤與非灰色（`N-7`）。
⛔ 被涵蓋門檻擋掉的個股**不得從畫面消失**，須另列「資料不足，未列入排序」清單到**個股層級**。

| 輸入 | 預期輸出 |
|---|---|
| `(0.0, None)` | `0.00`，正常色 |
| `(None, MISS_NOT_APPLICABLE)` | `N/A` 灰，未評估計數 **+0** |
| `(None, MISS_FETCH_FAILED)` | `⚠︎ —` ＋「看該列錯誤訊息…」，未評估計數 **+1** |
| `(None, MISS_NOT_ENOUGH)` | `⚠︎ —` ＋「**等時間累積（重跑無用）**」 —— ⛔ 不得顯示「可以重跑一次」 |
| `(None, MISS_NO_INPUT)` | `⚠︎ —` ＋「**上游這輪失敗，可以重跑一次**」 |

## §3 指標規格表

| 指標 | 算式（數學式） | 單位 | 門檻 SSOT（檔:符號） | 缺值行為（§1 三態） | 邊界（分母 0／負值／極值） | 應然 vs 實然 |
|---|---|---|---|---|---|---|
| 357 殖利率估值 | `y% = div ÷ P × 100`；分界價 `P_k = div ÷ YIELD_k_DEC` | `div` 元/股、`P` 元、`y` % | `shared/thresholds.py:YIELD_HIGH/MID/LOW(_DEC)` | `P<=0 or div<=0` → 不適用；`div is None` → 缺漏 | `y` 無上界 → sanity `(0,50]`，逾界 → `MISS_CONTRACT_DRIFT` | 設計變更 `D-07` |
| 本益比 PE | 不自算，取交易所公告值 | 倍 | 取數層無門檻 | `<=0` → 不適用；`NaN` → 缺漏 | 無上界 → sanity `(0,200]`，逾界 → 缺漏 | 設計變更 `D-08` |
| PB 分級 | `PB` 對照產業帶 | 倍 | `shared/stock_buckets.py:PB_BANDS_FINANCIAL/GROWTH/MFG`、`get_pb_bands` | `pb<=0` → 不適用 | 四級只三色 → 便宜／合理須可分辨 | 設計變更 `D-15` |
| PE 河流帶 | `P_band = TTM_EPS × k`；TTM `min_periods=4`，生效日＝季末+60d | 元 | **應下沉 L0** 並比照 PB 分產業 | TTM 序列空 → 缺漏 | ⛔ 序列空**不得**回 `0` | 實作 bug `D-13`／設計變更 `D-14` |
| 五桶 16 燈 | 純門檻分級（`high_bad`／`low_bad`／`band`） | 逐燈不同（`DangerSpec.unit`） | `shared/macro_buckets.py:BUCKET_DANGER_SPECS`、`SPECS_BY_KEY` | `None`／型別錯 → 缺漏（灰，不參與 worst 彙總） | `valid_min/max` 逾界 → `MISS_CONTRACT_DRIFT`；`wired=False` → **不適用** | 相同（本站最佳樣板） |
| 總經健康評分 | `h = Σ(vᵢwᵢ) ÷ Σwᵢ`，`i ∈ 有值` | 0~100 分 | `signal_thresholds.py:HEALTH_WEIGHT_JQ/SCORE`；`macro_thresholds.json:HEALTH_DEFENSE_THRESHOLD`、`BULL_MIN_SCORE` | 兩腿全缺 → 缺漏；單腿缺 → rescale ＋ `partial=True` | 宣告 [0,100]，實測值域被壓縮 → 須揭露 `partial` | 實作 bug `D-16` |
| 持股水位油門 | 分段查表 ＋ regime 否決 | 分／% | `shared/position_throttle.py:THROTTLE_HEALTH_A/B/DEF`、`THROTTLE_TIERS`、`THROTTLE_VETO_REGIMES` | `health is None` → 缺漏，**不渲染區間** | 輸入先 clamp `[0,100]`；`config:EXPOSURE_*` 是比例，差 100×，⛔ 不得混用 | 相同 |
| 235 燈 | 三軸（VIX／週線／`z=(週收−MA20w)÷std20w`）取最嚴重 | VIX 點、價 元、`z` σ | `shared/dividend_station_thresholds.py:VIX_LIGHT1~3`、`Z_LIGHT1~3`、`DEPLOY_*_PCT`、`MIN_WEEKS_FOR_BOLL` | 逐軸判可用性；三軸全缺 → **燈本身＝缺漏** | `_ok(v)` 須同時擋 `None` 與 `NaN` | 設計變更 `D-19` |
| 3-3-3 | 三子項布林 AND | 年／%／百分位比例 | `dividend_station_thresholds.py:MIN_INCEPTION_YEARS`、`MIN_ANN_RETURN_3Y_PCT`、`MIN_CUM_RETURN_3Y_PCT`、`PEER_TOP_FRACTION` | 三個 `*_ok` 已三態；`passed` 應同步三態 | 同類 ETF < `PEER_MIN_GROUP_SIZE` → **不適用**（非缺漏） | 設計變更 `D-18` |
| Sharpe | `(mean(r)·A − rf) ÷ (std(r)·√A)`，日 `A=252`／週 `A=52` | 無量綱 | `signal_thresholds.py:TRADING_DAYS_PER_YEAR`、`ETF_SHARPE_RF_FALLBACK_PCT` | `len<20` → 缺漏（`NOT_ENOUGH`）；`std==0` → 缺漏（`NO_VARIATION`） | ⛔ 三條路皆不得回 `0.0`；`0.0` 保留給「報酬＝rf」 | 實作 bug `D-03` |
| 最大回撤 MDD | `min((P − cummax(P)) ÷ cummax(P)) × 100` | %（≤0） | `config.py:MAX_PORTFOLIO_DRAWDOWN`（**比例**）；ETF 標準化端點應下沉 L0 | 例外／缺 `Close` → 缺漏 | 理論 [−100,0]；比例 vs % 差 100× | 實作 bug `D-25` |
| ATR 停損 | `Stop = Entry − m × ATR14`；備援 `Entry × (1 − pct/100)` | 元 | `signal_thresholds.py:ATR_STOP_FIXED_PCT`、`STOP_LOSS_DEFAULT_PCT`、`HARD_STOP_LOSS_PCT`；`config.py:STOP_LOSS_PCT`（比例） | `len<14` → **降級**（`method='fixed_8pct'`，非缺漏，須帶旗標）；例外 → 缺漏 | 量綱雙胞胎須併為單一 SSOT ＋ 推導 | 實作 bug `D-17` |
| 折溢價 | `premium% = (P − iNAV) ÷ iNAV × 100`（同日 inner-join ＋ 3 守門員） | % | `dividend_station_thresholds.py:PREMIUM_ALERT_PCT`；`signal_thresholds.py:ETF_PREMIUM_*_PCT` | `stale_nav` → 缺漏，不填該欄 | `iNAV<=0` → 缺漏（⛔ 不得除 0） | 相同 |
| 流動性 | 20日均量 ∧ AUM 取最嚴重 | 張／元→億（`÷1e8`） | `signal_thresholds.py:ETF_AVG_VOL_20D_LOW_LOTS`、`ETF_AVG_VOL_20D_FAIR_LOTS`、`ETF_AUM_LOW_YI`、`ETF_AUM_FAIR_YI` | 均量 `None` → 缺漏；AUM 型別錯 → **缺漏**（⛔ 不得 `except: pass`） | 換算後變數名須編碼單位（`aum_yi`） | 實作 bug `D-11` |
| RSI | Wilder RMA α=1/14：`100 − 100 ÷ (1 + gain÷loss)` | 0~100 | `config.py:RSI_OVERBOUGHT`、`RSI_OVERSOLD`；`signal_thresholds.py:RSI_STRONG_LOW`、`RSI_NEUTRAL_WEAK_LOW` | `len < period+1` → 缺漏 | `loss==0` → ε 映射 ~100（**已登記的刻意行為**，須註明非缺值） | 相同 |
| ATR | `TR=max(H−L,\|H−C₋₁\|,\|L−C₋₁\|)`，Wilder α=1/14 | 元 | `period=14` 與 `risk_control:ATR_MULTIPLIER` 應下沉 L0 | 缺 `high`/`low` → **缺漏**（⛔ 不得靜默退回 `close`） | 首根 `prev_close=NaN` → `TR=H−L`（合法） | 實作 bug `D-10` |
| KD | `RSV=(C−Lₙ)÷(Hₙ−Lₙ)×100`；`K=EWM(com=2)`，`D=EWM(K)` | 0~100 | `signal_thresholds.py:KD_OVERBOUGHT_LEVEL`、`KD_OVERSOLD_LEVEL` | `len<period` → 缺漏 | `Hₙ==Lₙ` → **`MISS_NO_VARIATION`**（⛔ 不得 `.replace(0,1)`） | 實作 bug `D-09` |
| 布林 | `MA20 ± 2σ(ddof=0)`；`bw=(U−L)÷MA×100` | 元／% | `signal_thresholds.py:BB_BW_SHRINK_WARN_RATIO`、`BB_BW_SHRINK_ACTION_RATIO` | 任一末值 `isna` → 缺漏 | `MA==0` → 換 `NaN` 再判（**正解樣板，勿改**） | 相同 |
| 乖離 BIAS | `(P − MAₙ) ÷ MAₙ × 100` | % | `src/config/config.py:MA_ANNUAL = 240`（**交易日**） | `P/MA is None or MA<=0` → 缺漏 | **`n < 240` → 缺漏（`NOT_ENOUGH`）**，⛔ 不得以短窗冒充年線乖離 | 設計變更 `D-12b` |
| 量比 | `今日量 ÷ 近 n 日均量` | 倍 | `signal_thresholds.py:VOLUME_RATIO_SURGE_HIGH/SURGE/MILD/DRY` | `len<n+1` 或均量 0 → 缺漏 | **`n` 須單一具名常數**，⛔ 不得一處 5 一處 20 卻共用同組門檻 | 實作 bug `D-26` |
| RS 相對強度 | 全市場百分位 → 0~100 | 分 | `signal_thresholds.py:STOCK_RS_STRONG_MIN`、`STOCK_RS_NEUTRAL_MIN` | `None` → 缺漏（**須與 🟡 中性不同色**） | 同組樣本不足 → 不適用 | 設計變更 `D-15` |
| 籌碼集中度 | `(外資+投信淨買賣超) ÷ 成交量` | % | `signal_thresholds.py:INST_NET_OUTLIER_VOLUME_RATIO`（異常徽章） | 缺 → 缺漏（⛔ 不得以 `0%` 頂替） | `0%` 屬**有值**（買賣超剛好抵銷） | 相同 |

**取捨標準**：依「**有 production caller ∧ 會渲染**」擇優；純內部中繼量、`wired=False` 的燈、已判定為死碼者不列。
評分型（個股健康／基本面四維／財報體檢／ETF 綜合分／選股網綜合分／組合綜合建議）移至 §4；純 delegate 的欄位（ETF「7%估值」→ `classify_yield_zone`、追蹤誤差 → caller 注入、IBS `(C−L)÷(H−L)`）沿用被委派者的規格，不另列。

## §4 評分型指標的評分表

**全站統一的缺值算分規則（⛔ 任一因子缺漏不得當 0 分，也不得給中性分）**

```
有效滿分 = Σ(滿分ᵢ)  for i ∈ {因子ᵢ 為「有值」}          # 不適用 與 缺漏 一律不進分母
if 有效滿分 == 0 or 有效滿分 < 總滿分 × SCREENER_MIN_FACTOR_COVERAGE_RATIO:
    return None, most_fundamental_miss([...])          # 不出分，畫面走 R-3 的「缺漏」分支
else:
    return round(Σ(得分ᵢ) ÷ 有效滿分 × 100, 1), None    # 附 partial=True, missing=[...]
```

| 指標 | 評分表（分數如何構成） | 總滿分 | 等第／星等門檻 SSOT |
|---|---|---|---|
| **個股健康評分** | 趨勢 30 ＋ RSI 20 ＋ 量比 15 ＋ KD 15 ＋ IBS 10 ＋ 布林 10 | 100 | `shared/health_thresholds.py:HEALTH_GRADE_A_MIN=80`、`HEALTH_GRADE_B_MIN=50` |
| **基本面四維** | 獲利 3 ＋ 成長 3 ＋ 股利 3 ＋ 估值 3（每維 0~3） | 12 | 估值維度**須改吃 `est_yield_pct`**（＝`div ÷ P × 100`）比 `thresholds.py:YIELD_HIGH/MID/LOW` |
| **財報體檢** | 11 項 `Status` → `_pts ∈ {+2,+1,−1,−2}`；`score% = Σpts ÷ (有效項數×2) × 100` | 22 | 分級樹門檻應下沉 `shared/financial_health_thresholds.py:FH_*` |
| **ETF 綜合分** | 7 維加權 `ret1y .25 / cagr3y .20 / sharpe .15 / mdd .15 / expense .12 / aum .08 / div_cv .05` | Σw=1.0 | `signal_thresholds.py:ETF_RATING_EXCELLENT/VERY_GOOD/GOOD/FAIR_MIN` |
| **選股網綜合分** | 5 因子全市場百分位取算術平均 | 100 | `signal_thresholds.py:SCREENER_MIN_FACTOR_COVERAGE_RATIO=0.5` |
| **組合綜合建議** | 健康 3/1 ＋ 多因子 3/1 ＋ 估值 2/1 ＋ 趨勢 1 → `pts` 分三級 | 9 | `health_thresholds.py:HEALTH_GRADE_A/B_MIN`；`signal_thresholds.py:MULTIFACTOR_GRADE_A_MIN/B_MIN`（**已存在，應改為引用**） |

⛔ **`in` 子字串比對不得用於控制流**：估值／趨勢維度須改吃**列舉碼**（`'cheap'/'fair'/'dear'/'overpriced'`），
字面與 emoji 只准出現在呈現層 —— 否則改一個字就改行為。
⛔ 評分型指標**必須有「⚪ 未評估」這一級**，且它與最差等第**不得同形**。

| 輸入 | 預期輸出 |
|---|---|
| 個股健康：趨勢 24/30、RSI 20/20，其餘 4 因子缺漏 | 有效滿分 50 ＝ 100×0.5，**未 `>` 門檻** → `(None, MISS_NO_INPUT)` |
| 個股健康：趨勢 24/30、RSI 20/20、量比 10/15，其餘缺漏 | 有效滿分 65 → `round(54÷65×100,1) = 83.1`、`partial=True`、`missing=['KD','IBS','布林']` |
| 基本面估值：`div=18.0` 元、`P=1000` 元 | `est_yield = 1.80%` → 估值 **0/3**（⛔ 不得因 `18.0 >= 7.0` 判 3/3，`P1-02`／`N-1`） |
| 基本面估值：`div=2.0` 元、`P=20` 元 | `est_yield = 10.00%` → 估值 **3/3** |
| 財報體檢：11 項中 2 項有值（有效滿分 4 < 22×0.5） | `grade='N/A'`、`score=None`、`⬜ 本輪不評等` —— ⛔ 少評項目不得讓等級**變好** |
| ETF 綜合分：`sharpe` 缺漏，其餘 6 維有值 | `Σw=0.85` rescale；⛔ `sharpe` 不得以 `0.0` 進 `_norm`（`P1-04`） |
| 組合綜合建議：四輸入全缺 | `(None, MISS_NO_INPUT)` → `⚪ 未評估`，⛔ 不得 `pts=0 → 最差級`（`P1-06`／`N-4`） |

## §5 應然 vs 實然差異清單

| 編號 | 一句話（**應然**；已知問題只引編號） | 檔案:符號 | 分類 |
|---|---|---|---|
| D-01 | 應回 `(None, MISS_NO_INPUT)` 而非 0 分（`P1-03`／`N-2`） | `src/compute/scoring/scoring_helpers.py:calc_health_score` | 實作 bug |
| D-02 | 估值維度應吃 `est_yield_pct`，簽章加 `price`（`P1-02`／`N-1`） | `scoring_helpers.py:calc_fundamental_score` | 實作 bug |
| D-03 | 三條返回路徑應回 `(None, MISS_NOT_ENOUGH/NO_VARIATION/CONTRACT_DRIFT)`（`P1-04`／`N-3`） | `src/compute/etf/etf_calc.py:calc_sharpe` | 實作 bug |
| D-04 | 四個輸入應 None-aware，禁 `default 0`／`default ''`（`P1-06`／`N-4`） | `src/ui/tabs/tab_helpers.py:final_recommendation` | 實作 bug |
| D-05 | 應新增「⚪ 未評估」級，與 `🔴 等待` 分離 | `tab_helpers.py:final_recommendation` | 設計變更 |
| D-06 | 三輸入全缺應回 `(None, MISS_NO_INPUT)`，禁 `or` 預設值（`P1-01`） | `shared/macro_compute.py:evaluate_market_status_v4_final` | 實作 bug |
| D-07 | 兩支分級函式的分界應真正一致（docstring 已自稱等價）（`P1-05`／`N-5`） | `shared/thresholds.py:classify_yield_zone`／`classify_stock_357_price` | 實作 bug |
| D-08 | `NaN` 與 `<=0` 應分流為缺漏／不適用（已知問題 #4） | `src/data/stock/yield_pe_fetcher.py:fetch_pe_name_maps` | 設計變更 |
| D-09 | 分母 0 應回 `MISS_NO_VARIATION`，禁 `.replace(0,1)` | `src/compute/strategy/tech_indicators.py:calc_kd` | 實作 bug |
| D-10 | 缺 `high`／`low` 應回缺漏，禁靜默退回 `close` | `src/compute/scoring/scoring_engine.py:compute_atr` | 實作 bug |
| D-11 | AUM 型別異常應回缺漏，禁 `except: pass`（`N-10`） | `etf_calc.py:calc_liquidity_score` | 實作 bug |
| D-12 | 三維全缺應回 `(None, MISS_NO_INPUT)`，禁輸出「三維未轉空」（`N-13`） | `src/compute/scoring/exit_signals.py:evaluate_exit_signals` | 實作 bug |
| D-12b | `n < 240` 應回缺漏，禁以短窗冒充年線乖離 | `src/compute/macro/macro_helpers.py:compute_twii_bias` | 設計變更 |
| D-13 | `_PE_BANDS` 應下沉 L0 SSOT（`N-6`／`N-12`） | `src/ui/tabs/stock_sections/section_357_valuation.py:_PE_BANDS` | 實作 bug |
| D-14 | PE 應比照 PB 依產業分帶（`N-6`） | `shared/stock_buckets.py:get_pb_bands`（新增 PE 對應） | 設計變更 |
| D-15 | `⚪`／灰應專屬「不適用／未評估」，中性結論改具名非灰（`N-7`） | `shared/thresholds.py:classify_yield_zone`；`tab_helpers.py:classify_rs_zone` | 設計變更 |
| D-16 | `max_score` 應輸出到 return dict（schema 自稱必存）（`N-9`） | `macro_helpers.py:calc_traffic_light` | 實作 bug |
| D-17 | 停損門檻應單一 SSOT ＋ 推導比例版（`N-11`） | `shared/signal_thresholds.py:STOP_LOSS_DEFAULT_PCT`；`src/config/config.py:STOP_LOSS_PCT` | 實作 bug |
| D-18 | `passed` 應三態，與三個 `*_ok` 同步 | `src/compute/etf/dividend_station.py:screen_333` | 設計變更 |
| D-19 | 三軸全缺時燈本身應為缺漏，非 `⚪ 巡航` | `dividend_station.py:light_235` | 設計變更 |
| D-20 | 單格缺漏應走 §4 有效滿分 rescale，禁「少評反而變好」 | `src/services/financial_health_engine.py:no_ai_overall_verdict` | 設計變更 |
| D-21 | 查無科目應回 `None`，禁 `return 0.0`（`C-R3`） | `src/data/core/financial_statements_fetcher.py:_v` | 實作 bug |
| D-22 | `except` 應回 `(None, MISS_CONTRACT_DRIFT)`，禁回傳部分結果 | `scoring_helpers.py:calc_fundamental_score` | 實作 bug |
| D-23 | 禁 `ffill().fillna(0).replace(inf,0)` 連用（`C-A3`） | `src/compute/strategy/v4_strategy_engine.py:__init__` | 實作 bug |
| D-24 | 被 `drop_unscored` 移除者應以「資料不足」清單呈現到個股層級（已知問題 #5） | `src/services/fundamental_screener_service.py:get_ranked_picks` | 設計變更 |
| D-25 | 常數名應編碼單位（比例 vs %，差 100×） | `src/config/config.py:MAX_PORTFOLIO_DRAWDOWN`／`EXPOSURE_*` | 實作 bug |
| D-26 | 量比視窗應單一具名常數，禁兩處不同窗共用同組門檻 | `tech_indicators.py:calc_volume_ratio` | 實作 bug |
| D-27 | 多因子切點應引用既有常數（現為 inline 75／55） | `tab_helpers.py:final_recommendation`；`signal_thresholds.py:MULTIFACTOR_GRADE_A_MIN/B_MIN` | 實作 bug |
