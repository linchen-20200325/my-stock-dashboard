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
