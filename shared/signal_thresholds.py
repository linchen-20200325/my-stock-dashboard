"""
shared/signal_thresholds.py — 訊號門檻 / 評分權重 SSOT (v18.241 群 E)

CLAUDE.md §3.3 反捏造 — 此檔集中本專案高嚴重度 inline magic number,
由原 13 處散落 inline 抽出為命名常數，調用端皆 import from shared/。

【新增常數需】
1. 附「為何選這值」的依據（資料來源 / 業務規則 / 歷史校準）
2. 在 CLAUDE.md §3.3 範圍 / 合理性表登記（如適用）
3. 變數名編碼單位（_PCT / _RATIO / _DAYS / _LOTS / _TWD）避免 §4.1 量綱陷阱

【SSOT 與其他 shared/ 檔分工】
- shared/thresholds.py     → 殖利率分級（YIELD_HIGH/MID/LOW）
- shared/health_thresholds.py → 健康評分分級（HEALTH_GRADE_A/B_MIN, DEFENSE_THRESHOLD）
- shared/ttls.py           → cache TTL 常數
- shared/signal_thresholds.py（本檔）→ 信號觸發 / 評分權重 / 領域邊界
"""

# ════════════════════════════════════════════════════════════════
# 時間 / 校準常數
# ════════════════════════════════════════════════════════════════

TRADING_DAYS_PER_YEAR: int = 252
"""年化常數：台股一年約 252 個交易日（IRR / 年化波動率 / Sharpe 等用）。
跨檔複用，原散落於 macro_signal_lookback_tw.py:238 + etf_calc.py:68"""


# ════════════════════════════════════════════════════════════════
# Macro 健康評分（macro_helpers.py compute_macro_health）
# ════════════════════════════════════════════════════════════════

HEALTH_WEIGHT_JQ: float = 0.4
"""景氣指標 (jq) 在健康評分的權重。原 macro_helpers.py:113 inline"""

HEALTH_WEIGHT_SCORE: float = 0.4
"""市場狀態評分 (/5*100) 在健康評分的權重。原 macro_helpers.py:113 inline"""

HEALTH_FNET_BONUS: int = 20
"""外資淨買超為正時的健康評分加分。原 macro_helpers.py:113 inline"""

CONFIDENCE_SOURCE_COUNT: int = 5
"""信心度計算的來源總數（PMI/CPI/M2/Foreign/VIX 等 5 大來源）。原 macro_helpers.py:148 inline"""


# ════════════════════════════════════════════════════════════════
# TW 麥邊訊號 lookback（macro_signal_lookback_tw.py compute_tw_macro_signals）
# ════════════════════════════════════════════════════════════════

FOREIGN_5D_NET_THRESHOLD_YI: float = -500.0
"""外資 5 日累積買賣超警戒值（單位：億 TWD）。
< -500 億 → 連續 5 日大賣超，配合大盤 20D 跌幅 -5% 才觸發紅旗。原 macro_signal_lookback_tw.py:280 inline"""

MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI: float = 3400.0
"""融資餘額過熱警戒值（單位：億 TWD）。
> 3400 億 → 散戶過度槓桿（歷史 P95 經驗值）。原 macro_signal_lookback_tw.py:288 inline"""

M1B_M2_GAP_DETERIORATION_THRESHOLD: float = -2.0
"""M1B/M2 缺口惡化警戒值（單位：pts/月，月差分）。
< -2 pts → 資金結構轉差（M2 成長 > M1B）。原 macro_signal_lookback_tw.py:296 inline"""

TWII_20D_DROP_THRESHOLD_PCT: float = -5.0
"""加權指數 20 日跌幅警戒值（單位：%）。
< -5% → 加速確認弱勢，配合其他訊號觸發紅旗。原 macro_signal_lookback_tw.py:304 inline"""


# ════════════════════════════════════════════════════════════════
# v4 Strategy Engine —市場狀態評估（v4_strategy_engine.py macro_risk_signal）
# ════════════════════════════════════════════════════════════════

VIX_HIGH_RISK_THRESHOLD: float = 25.0
"""VIX 高風險紅燈門檻。> 25 觸發紅燈，max_position=20%。原 v4_strategy_engine.py:76 inline"""

VIX_MEDIUM_RISK_THRESHOLD: float = 20.0
"""VIX 中風險黃燈門檻。> 20 觸發黃燈，max_position=50%。原 v4_strategy_engine.py:87 inline"""

FOREIGN_FUTURES_HIGH_RISK_THRESHOLD_LOTS: int = -20000
"""外資期貨高風險紅燈門檻（單位：口）。< -20000 口空單觸發紅燈。原 v4_strategy_engine.py:76 inline"""

FOREIGN_FUTURES_MEDIUM_RISK_THRESHOLD_LOTS: int = -10000
"""外資期貨中風險黃燈門檻（單位：口）。< -10000 口空單觸發黃燈。原 v4_strategy_engine.py:87 inline"""


# ════════════════════════════════════════════════════════════════
# scoring_engine — ATR % 風險分級
# ════════════════════════════════════════════════════════════════

ATR_PCT_LOW: float = 0.03
"""ATR% 低波動門檻（atr_pct = ATR14 / close）。< 3% → atr_score=2。原 scoring_engine.py:92 inline"""

ATR_PCT_HIGH: float = 0.05
"""ATR% 高波動門檻。3-5% → atr_score=1；> 5% → 0。原 scoring_engine.py:92 inline"""


# ════════════════════════════════════════════════════════════════
# exit_signals — 月線正乖離
# ════════════════════════════════════════════════════════════════

MA20_POSITIVE_DEVIATION_THRESHOLD_PCT: float = 15.0
"""月線（MA20）正乖離率警戒值（單位：%）。
> +15% → 月線正乖離過大，列入 bearish 警示條件。原 exit_signals.py:80 inline"""


# ════════════════════════════════════════════════════════════════
# v5_modules — 龍多股篩選
# ════════════════════════════════════════════════════════════════

CONTRACT_LIABILITY_YOY_GROWTH_THRESHOLD_PCT: float = 20.0
"""合約負債年增率（YoY）入選龍多股的門檻（單位：%）。
> 20% → 訂單能見度強。原 v5_modules.py:57 inline"""

CAPEX_TO_EQUITY_RATIO_THRESHOLD_PCT: float = 80.0
"""資本支出 / 股本比率入選龍多股的門檻（單位：%）。
> 80% → 大舉擴產訊號。原 v5_modules.py:58 inline"""


# ════════════════════════════════════════════════════════════════
# 市場狀態判斷 — market_strategy.market_regime()
# ════════════════════════════════════════════════════════════════

MARKET_BREADTH_NEUTRAL_PCT: float = 50.0
"""市場廣度（漲跌家數比 ad_ratio,0-100% 上漲家數佔比）中性分界。

> 50% → 廣度正向（多數個股上漲）；< 50% → 廣度偏弱。與 `shared/macro_buckets.py`
`adl` DangerSpec（yellow=50.0/red=35.0）同一尺度、同一資料源(`daily_data_fetchers.
fetch_adl` 的 `ad_ratio` 欄位)，避免同名參數在兩處用不同中心值（v18.449 修復:
`market_regime()` 原碼誤用 `ad_ratio > 1.0` 當門檻 + 預設值 1.0，屬「比值」尺度
語意，與實際資料源的「0-100% 百分比」尺度不符——預設值恰好等於門檻，導致此因子
從未真正生效過，UI 上「市場廣度」chip 永遠顯示同一個寫死 1.00。原 market_strategy.
py:107 inline `1.0`"""

# ════════════════════════════════════════════════════════════════
# ETF — 主動式 ETF 折溢價邊界
# ════════════════════════════════════════════════════════════════

ACTIVE_ETF_PREMIUM_MAX_PCT: float = 2.0
"""主動式 ETF |折溢價| 門檻（單位：%）。
> 2% → NAV 可能 stale。原 etf_calc.py:272 inline `_ACTIVE_PREM_MAX`"""

PASSIVE_ETF_PREMIUM_MAX_PCT: float = 3.0
"""被動式 ETF |折溢價| 合理上限（單位：%）。超過視為 NAV 過時配當日市價的假溢價。

v18.442:0050 production bug — 即時來源(yfinance navPrice / goodinfo)回「最後一筆
已公告淨值」並被 fetch_etf_nav_history 硬戳 `_last_bd`(今日)。若該 NAV 實為數日前值
(0050 案 104.03=06/29 淨值),配當日已上漲的市價(109.3)→ 同日 inner-join 成功、日期
守門員(G1/G3)全過(日期已被造假成今日),但算出假 +5.07%「嚴禁追高」。原 G2 上限守門員
只對主動式生效(`_is_active_etf`),被動式 0050 漏接 → 補此常數。

值 = 3.0 對齊 ETF_PREMIUM_HIGH_PREMIUM_PCT 帶頂(> 3% 原即「禁止追高」極端區):被動式
(尤其深度套利的大型市值型)真實溢價幾乎不越 1%,>3% 幾可斷定為 NAV 未更新;同時保留海外
連結型 ETF(如 00646)隔夜跳空的真實 1-3% 溢價顯示,避免誤殺。主動式(NAV T+1 易延遲)仍取
較嚴的 2%。§1 寧缺勿假:超限一律回 stale(顯示「NAV 資料延遲」)而非假折溢價。"""


# ════════════════════════════════════════════════════════════════
# Macro 通用領域邊界（macro_core.py / merrill_clock.py）v18.242 W3b
# ════════════════════════════════════════════════════════════════

RECESSION_LOGIT_COEF_SPREAD: float = -1.5
"""衰退機率 logit 回歸 — 利差 (10Y-3M) 係數。對齊 Fund 端同名常數。
logit = COEF_SPREAD * spread_10y3m + COEF_INTERCEPT,經 sigmoid → recession prob。
原 macro_core.py:1307 inline"""

RECESSION_LOGIT_COEF_INTERCEPT: float = -0.8
"""衰退機率 logit 回歸 — 截距項。原 macro_core.py:1307 inline"""

PMI_VALID_MIN: float = 30.0
"""PMI 採購經理指數合理下限（歷史極端衰退底部）。
< 30 視為解析錯誤過濾。對應 CLAUDE.md §3.2 + §4.2 不變量。原 merrill_clock.py:107 inline"""

PMI_VALID_MAX: float = 70.0
"""PMI 採購經理指數合理上限（歷史極端擴張頂部）。
> 70 視為解析錯誤過濾。原 merrill_clock.py:107 inline"""

MACRO_MERGE_ASOF_TOLERANCE_DAYS: int = 40
"""跨頻 merge_asof tolerance（單位：日曆日）。
月 macro vs 日 series 對齊用,40 日覆蓋一個月內任意營業日 backward join。
對應 CLAUDE.md §2.3 + §4.5 時序對齊。原 macro_core.py:1336 inline"""

MACRO_TREND_LOOKBACK_PERIODS: int = 6
"""macro snapshot trend arrow lookback 視窗（單位：期,月度資料即 6 個月）。
用於 make_indicator() 的 trend 箭頭計算。原 macro_core.py:1366 inline"""


# ════════════════════════════════════════════════════════════════
# 三大法人 sanity check(§3.2 v18.299)
# ════════════════════════════════════════════════════════════════

INST_NET_OUTLIER_VOLUME_RATIO: float = 5.0
"""三大法人單日買賣超 outlier 判定門檻(倍數)。
CLAUDE.md §3.2:|inst_net_shares| > 30D 均量 × 5.0 視為異常筆,可能為:
- 大宗交易 / 鉅額委託(非正常市場行為,投資判斷不能依此)
- FinMind/TWSE 解析錯誤(欄位錯位、單位誤判)
- 該股流動性極差(小型股,30D 均量本身偏低 → ratio 容易爆表)
觸發後 caller 應:(a) log 告警 + (b) 旗標 is_outlier=True,**不**靜默使用。

數值依據:依台股法人散戶結構,正常單日法人淨買賣超約 5-15% 均量。
> 5× 均量 = > 500% 比率,屬統計極端尾部,需人工檢視。"""


# ════════════════════════════════════════════════════════════════
# 個股組合（tab_stock_grp）— 操作狀態燈 + 多因子評級（v18.322 SSOT 化）
# 原 inline 散落於 tab_stock_grp.py / scoring_engine.py，本版抽出。
# 詳見 SPEC.md「個股組合評分門檻 SSOT」。同步退役「舊評分」(④ 汰弱留強改純健康度排)。
# ════════════════════════════════════════════════════════════════

GRP_VOL_SHRINK_RATIO: float = 0.7
"""操作狀態燈「量縮」判定：當日量 < 20 日均量 × 0.7。
配合健康度 A 級 + 多頭 + 近 20MA → 🔵 加碼燈（量縮打底蓄勢）。原 tab_stock_grp.py:299 inline"""

GRP_NEAR_MA20_BIAS_PCT: float = 3.0
"""操作狀態燈「近 20MA」判定：|MA20 乖離率| < 3%（單位：%）。
貼近月線視為位階健康，為 🔵 加碼燈條件之一。原 tab_stock_grp.py:300 inline"""

GRP_BIAS_OVERHEAT_WARN_PCT: float = 25.0
"""操作狀態燈「乖離過熱」警示：MA20 乖離率 > +25%（單位：%）→ 🟡 警示燈。
短線漲多偏離月線過大。原 tab_stock_grp.py:303 inline"""

GRP_NEWS_BEARISH_CONFIDENCE_MIN: float = 50.0
"""組合風控「利空新聞」採信門檻：AI 情緒 confidence ≥ 50 才計入利空。
低於 50 視為雜訊不計。原 tab_stock_grp.py:601 inline"""

MULTIFACTOR_GRADE_A_MIN: float = 75.0
"""多因子總分 A 級下限（0-100）。≥75 → A（強）。原 scoring_engine.py:355 inline。
與健康度分級（HEALTH_GRADE_A_MIN=80）為不同評分體系，門檻各自獨立。"""

MULTIFACTOR_GRADE_B_MIN: float = 55.0
"""多因子總分 B 級下限（0-100）。≥55 → B（中）；< 55 → C（弱）。原 scoring_engine.py:357 inline"""

MULTIFACTOR_ENTRY_MIN: float = 70.0
"""多因子總分「入選候選」門檻（0-100）。≥70 → 列為可進場候選（③ 多因子排行）。
原 tab_stock_grp.py:521 inline"""


# ════════════════════════════════════════════════════════════════
# scoring_engine 評分曲線 / 交易濾網斷點（v18.324 全抽，user 2026-06-27 指定）
# ─────────────────────────────────────────────────────────────────
# 說明：本區塊收 scoring_engine.py 各「判斷門檻」(value→score/label/signal 的比較斷點)。
# **不收**：指標視窗期(MA5/20/60/120、RSI14、ATR14、rolling 20)=TA 慣例非判斷門檻、
#   評分輸出值(2/1/0 子分、/6 /3 *100 正規化)=評分刻度結構、數學防呆(1e-10)、
#   年化倍數(×4)、日數慣例(360/365)、自然零界(>0)。
# 前綴分名（MOM_/RISK_/RS_/SQ_/FGMS_/LEAD_/CL_/BOLL_/FAKEOUT_/RR_/ATR_STOP_/
#   TIME_STOP_/VCP_/SQUEEZE_/POS_）確保「同數字不同義」不被硬湊成同一常數。
# ════════════════════════════════════════════════════════════════

# ── 動能分數（calc_momentum_score）────────────────────────────
MOM_SHARPE_GOOD: float = 0.5
"""Sharpe-like 動能（Return20/Sigma20 年化代理）優分門檻：>0.5 → 2 分。原 scoring_engine.py:89 inline"""

# ── 風險分數（calc_risk_score）波動率分級 ─────────────────────
RISK_VOL_VERYLOW_RATIO: float = 0.02
"""日波動率（20D std）極低門檻：<2% → +1 分（ETF/權值股）。原 scoring_engine.py:206 inline"""

RISK_VOL_LOW_RATIO: float = 0.035
"""日波動率正常低門檻：<3.5% → +1 分（原 3% 門檻已鬆寬）；≥3.5% 視為高波動高風險。原 scoring_engine.py:207 inline"""

# ── RS 相對強度（calc_rs_score）────────────────────────────────
# 無大盤基準時：個股絕對漲幅(%) 映射分數
RS_ABS_RET_T1_PCT: float = 50.0
"""RS 絕對漲幅 T1：≥50% → 100 分。原 scoring_engine.py:278 inline"""
RS_ABS_RET_T2_PCT: float = 30.0
"""RS 絕對漲幅 T2：≥30% → 90 分。原 scoring_engine.py:279 inline"""
RS_ABS_RET_T3_PCT: float = 15.0
"""RS 絕對漲幅 T3：≥15% → 75 分。原 scoring_engine.py:280 inline"""
RS_ABS_RET_T4_PCT: float = 5.0
"""RS 絕對漲幅 T4：≥5% → 60 分。原 scoring_engine.py:281 inline"""
# 有大盤基準時：RS = 個股漲幅 / |大盤漲幅| 分段
RS_BAND_T1: float = 2.0
"""RS 相對強度 T1：≥2.0 → 100 分（強勢）。原 scoring_engine.py:288 inline"""
RS_BAND_T2: float = 1.5
"""RS 相對強度 T2：≥1.5 → 90 分。原 scoring_engine.py:289 inline"""
RS_BAND_T3: float = 1.0
"""RS 相對強度 T3：≥1.0 → 75 分（與大盤同步）。原 scoring_engine.py:290 inline"""
RS_BAND_T4: float = 0.5
"""RS 相對強度 T4：≥0.5 → 55 分；≥0 → 40；<0 → 20（弱勢）。原 scoring_engine.py:291 inline"""

# ── RS σ 標準化超額報酬分級（calc_relative_strength / 抗跌 RS 選股）───────
# Mansfield 式：RS = (個股區間報酬 − 大盤區間報酬) / 大盤日報酬σ。單位 = σ（標準差倍數）。
# 用於「大盤下跌時仍贏過大盤」語意（比值法 RS_BAND 在大盤負報酬時會失真，故另立此組）。
RS_SIGMA_LEAD_MIN: float = 1.0
"""RS σ 領漲門檻：avg_rs ≥ +1.0σ → 🔴 逆勢強股（顯著強於大盤）。原 v5_modules.py:124 inline"""
RS_SIGMA_MILD_MIN: float = 0.3
"""RS σ 溫和抗跌門檻：avg_rs ≥ +0.3σ → 🟡 偏強（略強於大盤）。原 v5_modules.py:127 inline"""
RS_SIGMA_LAG_MAX: float = -0.3
"""RS σ 落後門檻：avg_rs < −0.3σ → 🟢 弱勢（弱於大盤，空頭優先出清）；[−0.3,0.3) → ⚪ 同步。原 v5_modules.py:130 inline"""

# ── 獲利品質 SQ（calc_quality_score）─────────────────────────
SQ_GM_TREND_DELTA_PCT: float = 1.0
"""毛利率趨勢顯著門檻：近2季均 - 前2季均 > +1pp → ↑；< -1pp → ↓；其間 → 持穩。原 scoring_engine.py:470 inline"""
SQ_REV_UP_RATIO: float = 1.02
"""營收趨勢↑門檻：近2季均 > 前2季均 × 1.02（成長>2%）。原 scoring_engine.py:477 inline"""
SQ_GM_LEVEL_HIGH_PCT: float = 50.0
"""毛利率絕對值高分線：≥50% → SGM=100。原 scoring_engine.py:488 inline"""
SQ_GM_LEVEL_LOW_PCT: float = 10.0
"""毛利率絕對值低分線：≤10% → SGM=40；10~50% 線性內插。原 scoring_engine.py:489 inline"""
SQ_GOOD_MIN: float = 75.0
"""SQ 獲利品質「優質」標籤下限（≠ 多因子總分 75，本為毛利×營收交叉品質分）。原 scoring_engine.py:496 inline"""
SQ_STABLE_MIN: float = 55.0
"""SQ「穩健」標籤下限。原 scoring_engine.py:497 inline"""
SQ_FAIR_MIN: float = 40.0
"""SQ「普通」標籤下限；< 40 → 弱。原 scoring_engine.py:498 inline"""

# ── 前瞻成長動能 FGMS（calc_forward_momentum_score）─────────
FGMS_W_CL: float = 0.40
"""FGMS 維度權重 — 合約負債動能。原 scoring_engine.py:657 inline"""
FGMS_W_INV: float = 0.30
"""FGMS 維度權重 — 存貨營收背離率。原 scoring_engine.py:657 inline"""
FGMS_W_THREE: float = 0.20
"""FGMS 維度權重 — 三率趨勢。原 scoring_engine.py:657 inline"""
FGMS_W_CAPEX: float = 0.10
"""FGMS 維度權重 — 資本支出強度。原 scoring_engine.py:657 inline"""
FGMS_CL_RATIO_STRONG: float = 0.5
"""合約負債 CL Ratio（最新CL/近4季均營收）強門檻：>0.5。原 scoring_engine.py:572 inline"""
FGMS_CL_RATIO_MID: float = 0.2
"""CL Ratio 中門檻：>0.2 → 55 分。原 scoring_engine.py:574 inline"""
FGMS_CL_RATIO_LOW: float = 0.05
"""CL Ratio 低門檻：>0.05 → 40 分。原 scoring_engine.py:575 inline"""
FGMS_CL_QOQ_UP_PCT: float = 10.0
"""CL QoQ 加速門檻：>10% → 動能向上。原 scoring_engine.py:572 inline"""
FGMS_CL_QOQ_DOWN_PCT: float = -10.0
"""CL QoQ 衰退門檻：<-10% → 20 分。原 scoring_engine.py:576 inline"""
FGMS_DIV_T1_PCT: float = 15.0
"""存貨營收背離率（Rev YoY - 存貨天數 YoY）T1：>15% → 100 分（賣得快）。原 scoring_engine.py:611 inline"""
FGMS_DIV_T2_PCT: float = 5.0
"""背離率 T2：>5% → 75 分。原 scoring_engine.py:612 inline"""
FGMS_DIV_T3_PCT: float = -5.0
"""背離率 T3：≥-5% → 50 分。原 scoring_engine.py:613 inline"""
FGMS_DIV_T4_PCT: float = -15.0
"""背離率 T4：≥-15% → 30 分；< -15% → 10 分。原 scoring_engine.py:614 inline"""
FGMS_REV_YOY_GOOD_PCT: float = 10.0
"""無背離資料時的營收 YoY 退路門檻：>10% → 65；>0 → 50；其餘 30。原 scoring_engine.py:617 inline"""
FGMS_RATE_DELTA_PCT: float = 0.5
"""三率（毛利/營益/淨利率）趨勢顯著門檻：近2季均 vs 前2季均差 > ±0.5pp 計入。原 scoring_engine.py:632 inline"""
FGMS_CAPEX_T1_PCT: float = 20.0
"""資本支出 YoY T1：>20% → 100 分（積極擴產）。原 scoring_engine.py:649 inline"""
FGMS_CAPEX_T2_PCT: float = -20.0
"""資本支出 YoY T2：>-20% → 45 分；≤-20% → 20 分。原 scoring_engine.py:651 inline"""
FGMS_LABEL_T1: float = 75.0
"""FGMS「前景亮麗」標籤下限。原 scoring_engine.py:679 inline"""
FGMS_LABEL_T2: float = 60.0
"""FGMS「動能向上」標籤下限。原 scoring_engine.py:680 inline"""
FGMS_LABEL_T3: float = 45.0
"""FGMS「持平觀察」標籤下限。原 scoring_engine.py:681 inline"""
FGMS_LABEL_T4: float = 30.0
"""FGMS「動能減弱」標籤下限；< 30 → 前景偏弱。原 scoring_engine.py:682 inline"""

# ── 基本面先行指標 narrative（calc_leading_indicators_detail）─
LEAD_CL_QOQ_SURGE_PCT: float = 20.0
"""I3 合約負債 QoQ 爆增：>20% → 🟢。原 scoring_engine.py:820 inline"""
LEAD_CL_QOQ_UP_PCT: float = 5.0
"""I3 合約負債 QoQ 穩健：>5% → 🟢；>-5% → 🟡 持平。原 scoring_engine.py:822 inline"""
LEAD_CL_QOQ_DOWN_PCT: float = -5.0
"""I3 合約負債 QoQ 下降：≤-5% → 🔴。原 scoring_engine.py:824 inline"""
LEAD_ASSET_DISPOSAL_RATIO: float = 2.0
"""I4/I5 重大資產處分偵測：處分資產現金流入 / CapEx_TTM > 2.0 → 事件驅動。原 scoring_engine.py:870,922 inline"""
LEAD_CAPEX_RATIO_CHG_UP_PCT: float = 15.0
"""I4 資本支出/營收比率 YoY 顯著上升：>15% → 🟢 積極擴產。原 scoring_engine.py:885 inline"""
LEAD_CAPEX_RATIO_CHG_DOWN_PCT: float = -20.0
"""I4 CapEx 比率 YoY 收縮容忍：>-20% → 🟡；≤-20% → 🔴 縮減投資。原 scoring_engine.py:891 inline"""
LEAD_INV_QOQ_DROP_PCT: float = -10.0
"""I5 存貨/銷售比 QoQ 大降：<-10% → 🟢 快速去化。原 scoring_engine.py:943,949 inline"""
LEAD_INV_QOQ_RISE_PCT: float = 15.0
"""I5 存貨/銷售比 QoQ 上升容忍：<15% → 🟡；≥15% → 🔴 積壓風險。原 scoring_engine.py:953 inline"""

# ── 大師級量化因子 check_*（v3.2）─────────────────────────────
CL_SURGE_YOY_PCT: float = 30.0
"""合約負債大增（隱形冠軍因子）YoY 門檻：>30% 且 ratio>10% → 隱形冠軍潛力。原 scoring_engine.py:1096 inline"""
CL_SURGE_RATIO_PCT: float = 10.0
"""合約負債/資本額比率門檻：>10%。原 scoring_engine.py:1096 inline"""
CL_GROWTH_YOY_PCT: float = 15.0
"""合約負債成長中標籤門檻：YoY >15%。原 scoring_engine.py:1099 inline"""
BOLL_BW_WIDE_PCT: float = 3.0
"""布林帶寬爆發門檻：今日帶寬 >3%。原 scoring_engine.py:1128 inline"""
BOLL_BW_TIGHT_PCT: float = 2.0
"""布林帶寬壓縮門檻：今日帶寬 <2% → 蓄勢待發。原 scoring_engine.py:1131 inline"""
BOLL_UPPER_PROXIMITY: float = 0.98
"""布林突破收盤逼近上軌比例：收盤 ≥ 上軌×0.98。原 scoring_engine.py:1128 inline"""
FAKEOUT_VOL_RATIO: float = 3.0
"""假突破爆量門檻：成交量 > 20日均量 ×3。原 scoring_engine.py:1153 inline"""
FAKEOUT_TAIL_RATIO: float = 0.6
"""假突破長上影線門檻：(最高-收盤)/(最高-最低) >0.6 → 主力出貨。原 scoring_engine.py:1153 inline"""
RS_STRONG_DAYS_MIN: int = 3
"""相對強度強勢股門檻：近N日中至少 3 天個股漲幅 > 大盤。原 scoring_engine.py:1179 inline"""

# ── 風控 / 部位（calc_rr_ratio / calc_atr_stop / check_time_stop / VCP / squeeze / position）──
RR_DEFAULT_TARGET_GAIN: float = 0.15
"""盈虧比預設目標漲幅：entry × (1+0.15) = +15%。原 scoring_engine.py:1190 inline"""
RR_MIN: float = 2.0
"""盈虧比通過門檻：≥2.0 才顯示（模組四剔除 <2）。原 scoring_engine.py:1196 inline"""
ATR_STOP_MULTIPLIER: float = 1.5
"""ATR 動態停損預設倍數：Stop = Entry - 1.5×ATR14。原 scoring_engine.py:978 inline default"""
ATR_STOP_FIXED_PCT: float = 8.0
"""ATR 計算失敗/資料不足時的固定停損百分比：8%（stop = entry×0.92）。原 scoring_engine.py:986,988 inline"""
TIME_STOP_MIN_GAIN: float = 0.02
"""時間停損最低報酬門檻：持有滿 max_days 但報酬 <2% → 建議換股。原 scoring_engine.py:1016 inline default"""
TIME_STOP_MAX_DAYS: int = 15
"""時間停損最大持有天數：超過 15 天且報酬不足 → 觸發。原 scoring_engine.py:1016 inline default"""
VCP_ATR_CONTRACTION_RATIO: float = 0.8
"""VCP 波動收縮確認：ATR5 < ATR20 ×0.8。原 scoring_engine.py:1050 inline"""
SQUEEZE_SHORT_RATIO_MIN: float = 0.3
"""軋空加分券資比門檻：>30%（short_ratio>0.3）。原 scoring_engine.py:1071 inline"""
SQUEEZE_INST_BUY_DAYS_MIN: int = 3
"""軋空加分法人連買門檻：≥3 天。原 scoring_engine.py:1071 inline"""
SQUEEZE_BONUS: int = 5
"""軋空加分分數：券資比+法人連買同時成立 → 總分 +5（上限 100）。原 scoring_engine.py:1072 inline"""
POS_MAX_RISK_PCT: float = 0.015
"""動態部位單筆最大虧損比例：總資金 ×1.5%。原 scoring_engine.py:1208 inline default"""
POS_ATR_MULTIPLIER: float = 1.5
"""動態部位停損 ATR 倍數：Stop = Entry - 1.5×ATR14。原 scoring_engine.py:1223 inline"""
POS_MAX_STOP_PCT: float = 0.85
"""動態部位最大停損保護：stop_loss 不低於 entry×0.85（最大停損 15%）。原 scoring_engine.py:1224 inline"""


# ════════════════════════════════════════════════════════════════
# 融資餘額警戒黃線 + 市場廣度 + macro_compass 殖利率（v18.326 PR-C 稽核 B 類）
# user 2026-06-27 跨檔稽核補抽。divergent 值各自具名（保行為），不一致處於 SPEC §15 旗標待統一。
# ════════════════════════════════════════════════════════════════

MARGIN_BALANCE_WARN_THRESHOLD_YI: float = 2500.0
"""融資餘額**黃線**警戒值（億 TWD）。> 2500 億 → 🟡 警戒（紅線 3400 見 MARGIN_BALANCE_OVERHEAT）。
v18.327：統一黃線（MK 籌碼面「提早預警」邏輯），SQL 邏輯卡片原 2800 已下修對齊本值。
原 daily_checklist:816 / tab_macro:949,986,2172,2186,4289 inline。"""

BREADTH_BULL_PCT: float = 60.0
"""市場廣度（jq_ratio / ADL 上漲佔比 %）多頭線：≥60% → 🟢 多頭積極 / bull regime。
原 tab_macro:880,1345-1348,4052-4053,4058-4059 inline。"""

BREADTH_NEUTRAL_PCT: float = 40.0
"""市場廣度中性/黃線：40~60% → 🟡 中性均衡 / neutral regime；< 40% → bear。
v18.327：統一黃線，「全市場健康度」beginner KPI(880) 原 30 已上修對齊本值（提供預警緩衝區）。
原 tab_macro:880,1345-1348,4052-4053,4058-4059 inline。"""

BREADTH_BEAR_PCT: float = 20.0
"""市場廣度位階標籤底線：≥20% → '20~40%' 位階；< 20% → '0~20%'（極弱）。原 tab_macro:1345 inline。"""

TNX_VALUATION_PRESSURE_PCT: float = 4.5
"""macro_compass 10Y 殖利率(TNX)估值壓力**紅線**：≥4.5% → 🔴 估值壓力（科技股不利）。
注意：與 MACRO_THRESHOLDS['US10Y'] 的 red_above=5.0 **刻意不同源**（compass 快訊用較嚴 4.5，
US10Y 桶 regime 用 5.0），屬不同用途。原 macro_core.py:499 inline。"""

TNX_NEUTRAL_PCT: float = 3.5
"""macro_compass TNX 中性**黃線**：3.5~4.5% → 🟡 中性區；< 3.5% → 🟢 寬鬆有利。原 macro_core.py:500 inline。"""


# ════════════════════════════════════════════════════════════════
# 進場操作層:停利停損 / 量比 / 趨勢分級(v18.328 PR-C 稽核三項違憲)
# user 2026-06-27 audit 提出 P1/P2/P3:個股 Tab 進場操作邏輯統一 SSOT,
# 兩 Tab(個股 / 個股組合)未來共用此處常數。
# ════════════════════════════════════════════════════════════════

# ── 停利停損(個股 Tab 進場操作建議區 / PR-C P2)──
STOP_PROFIT_T1_PCT: float = 5.0
"""停利目標 1:短線先入袋(+5%)。原 tab_stock.py:575 inline `_cur_p * 1.05`。"""

STOP_PROFIT_T2_PCT: float = 10.0
"""停利目標 2:波段目標(+10%)。原 tab_stock.py:576 inline `_cur_p * 1.10`。"""

STOP_LOSS_DEFAULT_PCT: float = 8.0
"""預設停損:跌破認賠(-8%)。原 tab_stock.py:577 inline `_cur_p * 0.92`。
注意:與 ATR_STOP_FIXED_PCT(8% / scoring_engine 風控)同值但語意分離 —
本常數是「個股 Tab 顯示用建議值」,後者是「ATR 失敗 fallback」。"""

# ── 量比軸線(個股三段 + 組合兩段,設計差保留但 SSOT 化 / PR-C P3)──
VOLUME_RATIO_SURGE: float = 1.5
"""量比異常放量:≥1.5× 20 日均量 → 🟢 強訊號。
個股 Tab 健康度卡片(原 inline 1.5)。原 tab_stock.py:1041 inline。"""

VOLUME_RATIO_MILD: float = 1.0
"""量比溫和放量:≥1.0× 但 <1.5× → 🟡 中性偏多。
個股 Tab 健康度卡片(原 inline 1.0)。原 tab_stock.py:1041 inline。"""

VOLUME_RATIO_DRY: float = 0.5
"""量比嚴重量縮:<0.5× 20 日均量 → 🟡 量能不足警示。
個股 Tab 警示列(原 inline 0.5)。原 tab_stock.py:1024 inline。

P2-3 v18.381 補:scoring_helpers.py:183 量比警戒(主力介入)門檻。"""

VOLUME_RATIO_SURGE_HIGH: float = 3.0
"""量比 >3.0× 視為重大消息 / 主力介入(scoring_helpers 評分)。

P2-3 v18.381:抽自 src/compute/scoring/scoring_helpers.py:183 inline。"""

CHINA_USDCNY_STRONG: float = 7.0
"""USDCNY <7.0 視為強勢人民幣(中國副盤評分 100 滿分)。
P2-3 v18.381:抽自 macro_helpers.py:947 inline。"""

CHINA_USDCNY_NEUTRAL: float = 7.2
"""USDCNY 7.0-7.2 中性區(評分 50)。C-3 v18.382 補抽。"""

CHINA_USDCNY_WEAK: float = 7.4
"""USDCNY 7.2-7.4 偏弱區(評分 25)、>7.4 大貶區(評分 0)。C-3 v18.382 補抽。"""

# ── RSI 帶區間評分(scoring_helpers 內 5 段)──────────────────
RSI_STRONG_LOW: float = 50.0
"""RSI 50-70 強勢區間(scoring_helpers.py:165 評分 20 滿分)。C-1 v18.382 抽自 inline。"""

RSI_NEUTRAL_WEAK_LOW: float = 40.0
"""RSI 40-50 中性偏弱(scoring_helpers.py:168 評分 12)。C-1 v18.382 抽自 inline。"""

# ── ETF 上下漲日數判定 ───────────────────────────────────────
ETF_UP_DOWN_DAYS_THRESHOLD: float = 60.0
"""ETF 近期上漲日 / 下跌日數 >60% 視為強弱訊號(etf_calc.py:901-907)。
C-2 v18.382 抽自 inline。觸發 🟡/🔴 燈號分流。

P2-3 v18.381 收尾:VOLUME_RATIO_SURGE_HIGH=3.0、CHINA_USDCNY_STRONG=7.0。

註:本檔下方仍有舊段 docstring,以下保留原樣不動。
注意:與 GRP_VOL_SHRINK_RATIO(0.7,組合 Tab 操作狀態燈量縮)刻意分開 —
個股用較嚴(0.5,嚴重量縮才警示),組合用較鬆(0.7,操作狀態燈),屬不同顆粒度設計。"""

# ── 趨勢分級 MA 配置(兩 Tab 應共用 / PR-C P1)──
TREND_USE_MA60: bool = True
"""趨勢判定主 MA 選擇:True=MA60(短中期更靈敏,個股 / 組合 Tab 統一);
False=MA100(舊組合 Tab 行為,保留旗標供 A/B 比較)。
原違憲:個股用 MA60 vs 組合用 MA100,同股雙 Tab 判斷反差。"""


# ════════════════════════════════════════════════════════════════
# ETF Tab 顯示閾值(v18.329 PR-D ETF audit 三項違憲)
# user 2026-06-27 audit:ETF 單檔 / 多檔 / 組合三 Tab inline magic 抽出。
# ════════════════════════════════════════════════════════════════

# ── ETF 基本閾值(PR-D P3)──
ETF_DIV_YOY_DECLINE_PCT: float = -10.0
"""ETF 配息 12M YoY 衰退警示:< -10% → 🔴 配息衰退。
原 etf_tab_single.py:228 inline `_div_yoy < -10`。"""

ETF_INCEPTION_YEARS_MIN: float = 3.0
"""ETF 成立年數最低門檻:≥ 3 年才算有完整週期樣本(避免追新 ETF)。
原 etf_tab_single.py:252 inline `_incept_yrs >= 3`。"""

ETF_CAGR_TARGET_PCT: float = 7.0
"""ETF 3Y CAGR 目標值:≥ 7% → 🟢 達標。對齊長期市場報酬基準。
原 etf_tab_single.py:244, etf_tab_grp_compare.py:78 兩處 inline `>= 7`。"""

ETF_TRACKING_ERROR_MAX_PCT: float = 1.5
"""ETF 追蹤誤差最大門檻:> 1.5% → 🟡 警示(追蹤效率不佳)。
原 etf_tab_single.py:410 inline `te > 1.5`。"""

# ── ETF 星等映射(C2 v18.402,4 段門檻 5 顆星)──
ETF_RATING_EXCELLENT_MIN: float = 0.80
"""ETF 加權分 5★(優異):score ≥ 0.80。"""

ETF_RATING_VERY_GOOD_MIN: float = 0.65
"""ETF 加權分 4★(很好):0.65 ≤ score < 0.80。"""

ETF_RATING_GOOD_MIN: float = 0.50
"""ETF 加權分 3★(尚可):0.50 ≤ score < 0.65。"""

ETF_RATING_FAIR_MIN: float = 0.35
"""ETF 加權分 2★(普通):0.35 ≤ score < 0.50;< 0.35 → 1★。
原 etf_scoring_helpers.py:78-87 + etf_quality.py:147-156 inline 4 數字共用。"""

# ── ETF 折溢價分級(PR-D P2,4 段)──
ETF_PREMIUM_DEEP_DISCOUNT_PCT: float = -2.0
"""ETF 折價深度買進區:≤ -2% → 🟢 建議買進(NAV 大幅折價)。
原 etf_tab_single.py:343 inline。"""

ETF_PREMIUM_FAIR_DISCOUNT_PCT: float = -0.5
"""ETF 折價合理區:-2% ~ -0.5% → 🔵 合理偏低。
原 etf_tab_single.py:347 inline。"""

ETF_PREMIUM_FAIR_PREMIUM_PCT: float = 1.0
"""ETF 中性 / 微溢價區:-0.5% ~ 1% → ⚪ 中性。
原 etf_tab_single.py:353 inline。"""

ETF_PREMIUM_HIGH_PREMIUM_PCT: float = 3.0
"""ETF 高溢價暫緩區:1% ~ 3% → 🔴 暫緩;> 3% → 🔴 禁止追高。
原 etf_tab_single.py:357 inline。"""

# ── σ 位階分級(PR-D P2,4 段 z-score)──
ETF_SIGMA_DEEP_BUY: float = -2.0
"""σ位階深度買進:z ≤ -2σ → 🟢 大買訊號(深度超賣)。
原 etf_tab_single.py:470 inline。"""

ETF_SIGMA_BUY: float = -1.0
"""σ位階買進:-2σ ~ -1σ → 🔵 小買(輕度超賣)。
原 etf_tab_single.py:473 inline。"""

ETF_SIGMA_REDUCE: float = 1.0
"""σ位階減碼:1σ ~ 2σ → 🟡 減碼(輕度過熱)。
原 etf_tab_single.py:476 inline。"""

ETF_SIGMA_STOP_PROFIT: float = 2.0
"""σ位階停利:≥ 2σ → 🔴 停利(深度過熱)。
原 etf_tab_single.py:479 inline。"""


# ════════════════════════════════════════════════════════════════
# ETF VCP 訊號最低資料量(v18.330 PR-E U-4)
# ════════════════════════════════════════════════════════════════

ETF_VCP_MIN_DAYS: int = 210
"""ETF VCP 形態判定最低資料量(交易日)。< 210 天 → 顯示「資料不足」不判 VCP。
210 ≈ 10 個月,確保有足夠樣本看到波幅收縮 + MA200 站上。
原 etf_calc.py:222 + etf_tab_single.py:344 兩處 inline `< 210` 重複。"""


# ════════════════════════════════════════════════════════════════
# ETF 流動性評分閾值(v18.330 PR-E U-6)
# 原 etf_calc.py:392-437 calc_liquidity_score 內 inline 4 處,本次抽 SSOT。
# ════════════════════════════════════════════════════════════════

ETF_AVG_VOL_20D_LOW_LOTS: int = 500
"""ETF 20 日均量流動性紅燈門檻(張)。< 500 張 → 🔴 流動性風險。原 etf_calc.py:416 inline。"""

ETF_AVG_VOL_20D_FAIR_LOTS: int = 1000
"""ETF 20 日均量流動性黃燈門檻(張)。500 ~ 1000 張 → 🟡 流動性偏弱。原 etf_calc.py:419 inline。"""

ETF_AUM_LOW_YI: float = 5.0
"""ETF AUM 規模紅燈門檻(億 TWD)。< 5 億 → 🔴 流動性風險。原 etf_calc.py:426 inline。"""

ETF_AUM_FAIR_YI: float = 10.0
"""ETF AUM 規模黃燈門檻(億 TWD)。5 ~ 10 億 → 🟡 流動性偏弱。原 etf_calc.py:429 inline。"""


# ════════════════════════════════════════════════════════════════
# ETF 衛星 σ 位階分級(quick_signals 用)(v18.331 PR-F U-7)
# 注意:與 ETF_SIGMA_DEEP_BUY/BUY/REDUCE/STOP_PROFIT(PR-D 抽,etf_tab_single 用)
# 是不同算法 — 本組是 etf_calc._quick_signals「跌了就買」5 段(MA20 ± n×σ),
# PR-D 那組是 etf_tab_single「年化波動率 z-score」4 段。兩組同為 σ 語意但顆粒不同。
# ════════════════════════════════════════════════════════════════

ETF_QUICK_SIGMA_DISASTER: float = 3.0
"""ETF 衛星 σ位階「股災價」:close < MA20 - 3σ → 🟢🟢🟢 大買 50%。
原 etf_calc.py:81 inline `3 * _std`。"""

ETF_QUICK_SIGMA_OVERSOLD: float = 2.0
"""ETF 衛星 σ位階「超跌價」:close < MA20 - 2σ → 🟢🟢 買 30%。
原 etf_calc.py:82 inline `2 * _std`。"""

ETF_QUICK_SIGMA_CHEAP: float = 1.0
"""ETF 衛星 σ位階「便宜價」:close < MA20 - 1σ → 🟢 小買 20%。
原 etf_calc.py:83 inline `1 * _std`。"""

ETF_QUICK_SIGMA_HIGH: float = 1.5
"""ETF 衛星 σ位階「偏高」:close ≥ MA20 + 1.5σ → 🟠 不追高 / 減碼。
原 etf_calc.py:84 inline `1.5 * _std`。"""

ETF_QUICK_SIGMA_OVERBOUGHT: float = 2.0
"""ETF 衛星 σ位階「準備停利」:close ≥ MA20 + 2σ → 🔴 分批停利。
原 etf_calc.py:85 inline `2 * _std`。與 OVERSOLD 同值但語意分離(下行 vs 上行)。"""


# ════════════════════════════════════════════════════════════════
# 個股 Tab 補強 SSOT(v18.331 PR-F U-10 / U-12 / U-13)
# user 2026-06-27 audit 殘留個股 Tab inline magic 收尾。
# ════════════════════════════════════════════════════════════════

# ── 布林帶邊界 2-tier(LOOSE warning / STRICT action,U-10 + Batch 5d v18.432)──
BB_NEAR_UPPER_RATIO: float = 0.97
"""布林帶「貼近上軌」LOOSE tier(3% tolerance):close >= upper × 0.97 → 強勢突破預警。
原 tab_stock.py:746 inline,U-10 v18.331 抽出。
caller:tab_stock.py / section_when_buy_sell.py / tech_indicators.py(calc_bollinger 結果 dict)
語意:篩選/掃描用,寬鬆判斷「靠近上軌」涵蓋更多 candidates。"""

BB_NEAR_UPPER_STRICT_RATIO: float = 0.995
"""布林帶「貼近上軌」STRICT tier(0.5% tolerance):close >= upper × 0.995 → 短線爆發買點(嚴格)。
v18.432 Batch 5d 抽出。
caller:src/compute/strategy/v5_modules.py:247(布林通道訊號 fn)
語意:訊號層 action,嚴格門檻避免假突破誤判;與 LOOSE 0.97 形成 2-tier 漸進判讀。"""

BB_DROP_OUT_RATIO: float = 0.95
"""布林帶「跌出上軌」訊號:close < upper × 0.95 且 close > ma → 動能轉弱。
原 tab_stock.py:747 inline。"""

# ── 布林帶寬收縮 2-tier(Phase 2 Batch 5b v18.429)──
BB_BW_SHRINK_WARN_RATIO: float = 0.7
"""布林帶寬「收縮警示」threshold:bw < bw_mean × 0.7 → KPI 變綠 / 「帶寬極縮 ⚡」標籤。
3 caller:section_health_score.py:152,153 + section_vcp_bollinger.py:71"""

BB_BW_SHRINK_ACTION_RATIO: float = 0.6
"""布林帶寬「極度收縮」action threshold:bw < bw_mean × 0.6 → 訊號框 + verdict
「布林帶寬極度收縮:即將爆發」。2 caller:section_vcp_bollinger.py:77,91。
SSOT 設計:warn(0.7)→ action(0.6)兩 tier 漸進判讀。"""

# ── RS 帶狀(U-12)──
STOCK_RS_STRONG_MIN: float = 75.0
"""個股 RS 相對強度「強勢」門檻:RS ≥ 75 → 跑贏大盤明顯。
原 tab_stock.py:809 inline。"""

STOCK_RS_NEUTRAL_MIN: float = 50.0
"""個股 RS 相對強度「中性」門檻:50 ≤ RS < 75 → 與大盤同步。
< 50 → 弱勢(落後大盤)。原 tab_stock.py:809 inline。"""

# ── 月線乖離(U-13)──
STOCK_BIAS_OVERHEAT_PCT: float = 20.0
"""個股年線(MA240)正乖離過熱警示:bias > +20% → 分批出場建議。
原 tab_stock.py:981 inline `_bias_i > 20`(已部分使用 SSOT 化)。"""

STOCK_BIAS_DEEP_DEVIATION_PCT: float = 20.0
"""個股年線負乖離布局區:bias < -20% → 左側布局訊號。
原 tab_stock.py:952 inline `_bias_i < -20`。與 OVERHEAT 同值但語意分離。"""

STOCK_BIAS_MILD_DEVIATION_PCT: float = 15.0
"""個股月線(MA20)中度乖離警示:|bias| > 15% → 短線過熱 / 過冷。
原 tab_stock.py:803/830/832 inline 多處。"""


# ════════════════════════════════════════════════════════════════
# ETF 投組 Tab 投組特有 SSOT(v18.332 PR-G U-9)
# 2026-06-28 etf_tab_portfolio.py 深度 audit 殘留 8 處 inline magic 收斂。
# 投組層特有(single/grp 不消費):分散度、再平衡、壓測、VaR。
# ════════════════════════════════════════════════════════════════

# ── 再平衡(G1 P3)──
PORTFOLIO_REBAL_TOLERANCE_DEFAULT_PCT: float = 5.0
"""ETF 投組再平衡容忍偏離預設值 %:|實際-目標| > 5% → 觸發再平衡建議。
Slider 範圍 1-15,預設 5。原 etf_tab_portfolio.py:86 inline。"""

# ── 分散度(G1 P1+P2)──
ETF_CORR_HIGH_THRESHOLD: float = 0.85
"""ETF 投組相關係數「同質性過高」警示:任兩檔 Pearson corr > 0.85
→ ⚠️ 資產同質性過高。原 etf_tab_portfolio.py:493 inline。"""

PORTFOLIO_OVERLAP_WEIGHT_THRESHOLD_PCT: float = 30.0
"""ETF 持股重疊(權重 Overlap%)警示:任兩檔權重共同持股加總 > 30%
→ ⚠️ 建議擇一保留。原 etf_tab_portfolio.py:549 inline(weight branch)。"""

PORTFOLIO_OVERLAP_JACCARD_THRESHOLD_PCT: float = 50.0
"""ETF 持股重疊(Jaccard 集合)警示:|A∩B|/|A∪B| > 50%
→ ⚠️ 建議擇一保留。原 etf_tab_portfolio.py:549 inline(jaccard branch)。"""

# ── 壓力測試(G2)──
PORTFOLIO_STRESS_TEST_DROP_PCT: float = -20.0
"""ETF 投組壓力測試 S&P500 下跌幅度(%):用於估算 Beta 加權虧損。
業界常用 -20% 中型空頭情境。原 etf_tab_portfolio.py:618 inline `-0.20`。"""

PORTFOLIO_STRESS_TEST_LOSS_WARN_PCT: float = 20.0
"""ETF 投組壓測虧損警示門檻(%):組合預估虧損 > 20%
→ ⚠️ 尾部風險超標,建議增加避險。原 etf_tab_portfolio.py:627/630/632 inline。"""

# ── VaR 風險值(G2)──
PORTFOLIO_VAR_95_PERCENTILE: float = 0.05
"""ETF 投組 VaR 95% 信心區間分位數:quantile(0.05)。
歷史模擬法取最差 5% 分位數,即「100天中95天虧損不超過此值」。
原 etf_tab_portfolio.py:664 inline。"""

PORTFOLIO_VAR_99_PERCENTILE: float = 0.01
"""ETF 投組 VaR 99% 信心區間分位數:quantile(0.01)。
歷史模擬法取最差 1% 分位數(更保守的尾部評估)。
原 etf_tab_portfolio.py:665 inline。"""

PORTFOLIO_VAR_MONTHLY_WARN_PCT: float = 10.0
"""ETF 投組月度 99% VaR 警示門檻(%):月度尾部虧損 > 10%
→ ⚠️ 尾部風險偏高,建議增加防禦部位。原 etf_tab_portfolio.py:689/693/699 inline。"""


# ════════════════════════════════════════════════════════════════
# v18.436「全做」audit 翻案 — 8 處 inline magic 收 SSOT(#3-10)
# user 2026-06-30 全域深挖 audit 找出;此段補抽,語意化各門檻。
# ════════════════════════════════════════════════════════════════

# ── #3 外資期貨防禦訊號(macro_helpers 健康評分)──
FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD: int = 30000
"""外資期貨淨部位「大空單防禦訊號」門檻(單位:口,絕對值)。
macro_helpers.compute_macro_health:健康評分 <2 且外資淨空單 |部位| >30000 口
且方向為空(<0)→ 觸發 _defense 防禦旗標。約 75 億 TWD 規模。
原 src/compute/macro/macro_helpers.py:92 inline。注意:與 v4_strategy_engine 的
FOREIGN_FUTURES_HIGH/MEDIUM_RISK(-20000/-10000)語意不同 — 後者是分級紅黃燈,
本常數是健康評分內的單一防禦觸發,刻意分離。"""

# ── #4 VPOC 套牢賣壓距離(v4_strategy_engine Task 3)──
VPOC_PRESSURE_DISTANCE_THRESHOLD: float = 0.15
"""VPOC(體積加權最大量價位)套牢賣壓距離門檻(比例,0.15=15%)。
當前價 < VPOC 且 (VPOC-現價)/現價 < 0.15 → 判定上方有近 N 日最大量套牢賣壓。
原 src/compute/strategy/v4_strategy_engine.py:214 inline。"""

# ── #5 ETF 基金經理新任門檻(etf_calc 經理人燈號)──
ETF_MANAGER_TENURE_NEW_DAYS: int = 180
"""ETF 基金經理「新任」判定門檻(單位:天,約 6 個月)。
任期 <180 天視為新經理人,表現待觀察 → UI 顯示「再給時間」建議。
原 src/compute/etf/etf_calc.py:915 inline。"""

# ── #6 FGMS 存貨營收背離 — 無背離資料時的 YoY 退路評分 ──
FGMS_NO_DIV_GOOD_SCORE: int = 65
"""FGMS 存貨/營收背離無 inv_days 資料時:營收 YoY >FGMS_REV_YOY_GOOD_PCT(10%)
→ 退路評分 65。原 src/compute/scoring/scoring_engine.py:654 inline。"""

FGMS_NO_DIV_POSITIVE_SCORE: int = 50
"""FGMS 退路:營收 YoY >0 但未達 good → 評分 50。原 scoring_engine.py:654 inline。"""

FGMS_NO_DIV_DECLINE_SCORE: int = 30
"""FGMS 退路:營收 YoY <=0 → 評分 30。原 scoring_engine.py:654 inline。"""

# ── #7 KD 超買 / 超賣邊界(scoring_helpers 健康度 KD 評分)──
KD_OVERBOUGHT_LEVEL: float = 80.0
"""KD 高檔區邊界:K>80 黃金交叉視為「高檔黃叉注意」(評分降)。
原 src/compute/scoring/scoring_helpers.py:222 inline。"""

KD_OVERSOLD_LEVEL: float = 20.0
"""KD 低檔區邊界:K>20 且死亡交叉視為一般死叉(評分 5);K<=20 為超賣不另扣。
原 src/compute/scoring/scoring_helpers.py:225 inline。與 KD_OVERBOUGHT_LEVEL 對稱。"""

# ── #9 IBS(內結構 Internal Bar Strength)反彈 / 賣壓邊界 ──
IBS_OVERSOLD_THRESHOLD: float = 0.2
"""IBS 收低門檻(比例):IBS<=0.2(收當日區間低 20% 內)→ 隔日易反彈(評分 +10)。
原 src/compute/scoring/scoring_helpers.py:207 inline。"""

IBS_OVERBOUGHT_THRESHOLD: float = 0.8
"""IBS 收高門檻(比例):IBS>=0.8(收當日區間高 20% 內)→ 隔日易賣壓(評分 +2)。
原 src/compute/scoring/scoring_helpers.py:210 inline。"""

# ── #10 18 個月回測完整度門檻(tw_backtest 拐點驗證)──
BACKTEST_18M_DAYS_THRESHOLD: int = 547
"""18 個月前向報酬「資料完整」判定門檻(單位:日,547≈18.2 月)。
拐點事件距今 >=547 天且 r18 非空 → 標記該事件回測完整。
原 src/compute/strategy/tw_backtest.py:218-219 inline(同值寫兩處)。"""
