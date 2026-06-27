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
# ETF — 主動式 ETF 折溢價邊界
# ════════════════════════════════════════════════════════════════

ACTIVE_ETF_PREMIUM_MAX_PCT: float = 2.0
"""主動式 ETF |折溢價| 門檻（單位：%）。
> 2% → NAV 可能 stale。原 etf_calc.py:272 inline `_ACTIVE_PREM_MAX`"""


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
注意:與 GRP_VOL_SHRINK_RATIO(0.7,組合 Tab 操作狀態燈量縮)刻意分開 —
個股用較嚴(0.5,嚴重量縮才警示),組合用較鬆(0.7,操作狀態燈),屬不同顆粒度設計。"""

# ── 趨勢分級 MA 配置(兩 Tab 應共用 / PR-C P1)──
TREND_USE_MA60: bool = True
"""趨勢判定主 MA 選擇:True=MA60(短中期更靈敏,個股 / 組合 Tab 統一);
False=MA100(舊組合 Tab 行為,保留旗標供 A/B 比較)。
原違憲:個股用 MA60 vs 組合用 MA100,同股雙 Tab 判斷反差。"""
