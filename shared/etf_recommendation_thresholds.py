"""ETF 多檔比較「留 / 觀察 / 換」建議門檻 SSOT(v19.64)。

多檔 ETF 比較表已算出 綜合分 / 星等 / 流動性 / 配息健康 / 估值 / σ位階 等欄,
但 user 反映「看不出來哪些留、哪些賣」。本模組收「把這些既有分數 → 一句話行動
建議」用到的**數字門檻 + 語意標籤**,禁止散落 inline magic number(§3.3)。

判斷不重算任何指標,純粹讀 `compute_etf_composite_score` 等既有輸出再分級,
因此門檻只有「綜合分切點」與「σ位階偏貴/偏便宜切點」兩組。

設計:純常數模組,零 import 依賴。caller 用
`from shared.etf_recommendation_thresholds import KEEP_COMPOSITE_MIN, ...`。
"""
from __future__ import annotations

# 綜合分切點(對齊 shared/signal_thresholds.py:ETF_RATING_*;此處是「行動」層再分級)。
# ≥ KEEP_COMPOSITE_MIN(=4★ 門檻 0.65)→ 體質佳,基本盤是「留」。
KEEP_COMPOSITE_MIN: float = 0.65
# < SELL_COMPOSITE_MAX(=1★/2★ 交界 0.35)→ 體質偏弱,基本盤是「考慮換」。
# 介於兩者之間 → 「觀察」。
SELL_COMPOSITE_MAX: float = 0.35

# σ位階(現價離 252 日均線幾個 σ)偏便宜 / 偏貴切點 —— 只影響「加碼時機」註解,
# 不改變留/換判斷(好 ETF 貴了也是續抱、暫緩加碼,而非賣出)。
SIGMA_Z_CHEAP: float = -1.0   # ≤ 此 → 價位偏低,分批加碼時機較佳
SIGMA_Z_RICH: float = 1.0     # ≥ 此 → 價位偏高,續抱可、暫緩加碼

# 同類重疊:同一 ETF 類別(市值型 / 高股息 …)持有幾檔(含)以上就提示「擇一」。
REDUNDANCY_MIN_PEERS: int = 2

# 版本(改公式或門檻時 bump;provenance / golden test 用)。
ETF_RECOMMENDATION_VERSION: str = "etf_recommendation_v1"

# 建議動作 → 中文語意標籤(UI 顯示 + golden test 釘一致)。
VERDICT_KEEP: str = "留下"
VERDICT_WATCH: str = "觀察"
VERDICT_SWITCH: str = "考慮換"
VERDICT_NA: str = "資料不足"

VERDICT_ICONS: dict[str, str] = {
    VERDICT_KEEP: "✅",
    VERDICT_WATCH: "⚠️",
    VERDICT_SWITCH: "🔻",
    VERDICT_NA: "⬜",
}
