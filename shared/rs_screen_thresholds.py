"""shared/rs_screen_thresholds.py — 抗跌 RS 選股（大盤下跌時仍贏過大盤）L0 SSOT（v19.70）。

只放本篩選器**新的**表現/設定常數：排行檔數、lookback 視窗預設、分級標籤/圖示、版本。
σ 分級門檻（1.0 / 0.3 / -0.3）**重用** `shared/signal_thresholds.py` 的 `RS_SIGMA_*`，
不在此重複定義（避免同數字兩處各改一半）。
"""
from __future__ import annotations

# ── 排行 / 掃描設定 ────────────────────────────────────────────
RS_LEADER_TOP_N: int = 50
"""排行取前 N 檔（使用者需求：抗跌 RS 前 50）。"""

RS_DEFAULT_LOOKBACK: int = 60
"""預設 lookback（交易日）：60 ≈ 近 3 個月，中線抗跌最常用。"""

# UI lookback 選項（label → 交易日數）。值沿用 calc_relative_strength 既有多週期慣例。
RS_LOOKBACK_PRESETS: dict[str, int] = {
    "短線（近 1 月 / 20 交易日）": 20,
    "中線（近 3 月 / 60 交易日）": 60,
    "波段（近半年 / 120 交易日）": 120,
}

RS_MIN_ALIGNED_ROWS: int = 20
"""個股與大盤對齊後至少要有的共同交易日數（<此 → 資料不足，不硬算）。"""

RS_SCAN_MAX: int = 400
"""單次掃描深掃檔數硬上限（~324 存活池 + 餘裕；超過會於 note 揭露被截斷，§5 不靜默）。"""

RS_MAX_WORKERS: int = 8
"""逐檔抓價的並行 thread 數（fetch_stock_history_1y 無 st.cache、thread-safe）。"""

# ── 分級標籤 / 圖示（TW 慣例：紅=強、綠=弱）────────────────────
TIER_LEAD: str = "逆勢強股"        # avg_rs ≥ RS_SIGMA_LEAD_MIN
TIER_MILD: str = "偏強抗跌"        # avg_rs ≥ RS_SIGMA_MILD_MIN
TIER_SYNC: str = "同步大盤"        # RS_SIGMA_LAG_MAX ≤ avg_rs < MILD
TIER_LAG: str = "落後大盤"         # avg_rs < RS_SIGMA_LAG_MAX
TIER_INSUFFICIENT: str = "資料不足"

TIER_ICONS: dict[str, str] = {
    TIER_LEAD: "🔴",   # 紅 = 逆勢最強（TW 慣例，紅為漲）
    TIER_MILD: "🟡",
    TIER_SYNC: "⚪",
    TIER_LAG: "🟢",    # 綠 = 弱勢落後
    TIER_INSUFFICIENT: "⚫",
}

# 可進排行（前 50）的分級（資料不足不列入排行）。
RS_RANKABLE_TIERS: tuple[str, ...] = (TIER_LEAD, TIER_MILD, TIER_SYNC, TIER_LAG)

RS_LEADER_VERSION: str = "rs_leader_v1"
