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
