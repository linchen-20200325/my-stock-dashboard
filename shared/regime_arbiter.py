"""大盤 regime 唯一仲裁點（L0 純函式，C1 v19.182）。

問題（2026-08-07 稽核 C1）
--------------------------
同一天、同一份資料下，全站有 **4 個各自為政的 regime producer**：

======  =================================================  ==================================
代號    算法                                               消費端
======  =================================================  ==================================
P1      `calc_traffic_light()` 的 if/elif 決策樹           總經頁燈號卡 / 戰情概覽 / 今日作戰室
        （消費端再由 **icon 反推** regime）                / 5 分鐘清單 / section_news_ai
P2      raw `mkt_info['regime']` → `warroom_summary`       置底常駐條 / ETF 配置橫幅
        → `get_macro_state()` → `AllocationDecision`       / 個股頁加碼三問 / 個股組合評分
P3      `mkt_info.get('regime', 'neutral')` 直讀           ETF 核衛目標 60/40 vs 70/30
        （未載入時**捏造** 'neutral'）                     / ETF AI prompt
P4      `warroom_summary['traffic_light']` 中文 substring  個股組合 🚦 大盤燈號卡
======  =================================================  ==================================

P1 的決策樹在 `defense`（大盤評分 <2 且外資期貨大額淨空）或
`health < HEALTH_DEFENSE_THRESHOLD` 時**直接判 🔴，完全不看 `mkt_info['regime']`**。
於是 `regime='bull'` 但健康分低的那天，總經頁上半印 🔴 空頭防禦、頁底常駐條印
🟢 多頭市場、ETF 頁還照多頭 60/40 配核衛 —— 三個畫面三個答案。

設計（§2.1 SSOT：衝突時上層贏，禁止平均）
------------------------------------------
本模組是**唯一**把「輸入 → regime 判定」的那條決策樹寫成 code 的地方：

- `arbitrate_regime()` —— 唯一仲裁函式，回 `RegimeVerdict`
  （`regime` 英文 canonical ／ `light` 🟢🟡🔴⬜ ／ `source` 哪條分支生效 ／
  `defense` ／ `is_loaded`）。
- `calc_traffic_light`（L2）呼叫它決定燈色與文案 —— 燈號與 canonical regime
  **出自同一次呼叫**，結構上不可能再打架（不再需要「由 icon 反推 regime」）。
- `get_macro_state`（L3）呼叫它產生全站 canonical 契約。

三態（§1 Fail Loud）
--------------------
未載入 → `UNLOADED_VERDICT`（`regime='unknown'` / `light='⬜'` /
`source='unloaded'` / `is_loaded=False`）。**絕不退回 `'neutral'`** ——
「不知道」與「判斷為震盪」是兩件事，後者會讓消費端照常跑完整套判定。

分層（§8.2）
------------
L0 Infra：只 import `shared.*`（`macro_calibration` / `signal_thresholds`），
零 L1+ 依賴、不 import streamlit、無 I/O（門檻讀檔已封裝在 `macro_calibration`）。

caller::

    from shared.regime_arbiter import arbitrate_regime, UNLOADED_VERDICT
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

# L0 → L0：門檻 SSOT。macro_thresholds.json 由季度 recalibrate workflow 寫入。
from shared.macro_calibration import load_calibrated_thresholds
from shared.signal_thresholds import FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD

# ── 燈號字面 SSOT ────────────────────────────────────────────────────────
LIGHT_BULL: str = '🟢'
LIGHT_NEUTRAL: str = '🟡'
LIGHT_BEAR: str = '🔴'
LIGHT_UNKNOWN: str = '⬜'

#: regime → 燈號。`caution` 與 `bear` 同為 🔴（`position_throttle`
#: `THROTTLE_VETO_REGIMES` 已把兩者同列否決，此處對齊）。
REGIME_LIGHT: dict[str, str] = {
    'bull':    LIGHT_BULL,
    'neutral': LIGHT_NEUTRAL,
    'caution': LIGHT_BEAR,
    'bear':    LIGHT_BEAR,
    'unknown': LIGHT_UNKNOWN,
}

# ── 生效分支識別碼 SSOT（`source` 欄位；畫面 / log / 測試共用）──────────────
SOURCE_DEFENSE_FUTURES: str = 'defense:foreign_futures'
"""大盤評分 < DEFENSE_MAX_MARKET_SCORE 且外資期貨大額淨空 → 強制防禦。"""

SOURCE_DEFENSE_HEALTH: str = 'defense:health_below_threshold'
"""總經健康分 < HEALTH_DEFENSE_THRESHOLD → 強制防禦。"""

SOURCE_BULL_SCORE: str = 'bull:score'
"""趨勢 regime=bull 且大盤評分 ≥ BULL_MIN_SCORE → 多頭。"""

SOURCE_BEAR_TREND: str = 'bear:trend_regime'
"""趨勢 regime ∈ {caution, bear} → 保守防禦。"""

SOURCE_NEUTRAL_FALLTHROUGH: str = 'neutral:fallthrough'
"""以上皆不成立 → 震盪整理（決策樹的 else）。"""

SOURCE_UNLOADED: str = 'unloaded'
"""總經未評估。**不是**一種市場判斷。"""

SOURCE_FILE_RULE_ENGINE: str = 'macro_state.json:rule_engine'
"""warroom 未載入、退到 macro_state.json 的 `calculate_system_state` 曝險分級。"""

# ── 門檻 ────────────────────────────────────────────────────────────────
DEFENSE_MAX_MARKET_SCORE: int = 2
"""外資期貨防禦訊號要求的「大盤評分上限」（評分 < 本值才可能觸發）。

原為 `macro_helpers.calc_traffic_light` 內的 inline 裸數字 `2`
（`_score < 2`），C1 v19.182 抽出具名（§3.3 反捏造）。**數值完全未變**。
語意：外資重兵空單只有在大盤趨勢本身也弱（6 項訊號中拿不到 2 分）時
才升級為防禦訊號；趨勢強勁時的期貨空單視為避險而非轉空。
"""


def _to_float(value: Any) -> Optional[float]:
    """容錯轉 float：None / 非數字 / NaN → None（§1：不捏造 0）。"""
    if value is None:
        return None
    try:
        _f = float(value)
    except (TypeError, ValueError):
        return None
    return None if _f != _f else _f  # NaN guard


@dataclass(frozen=True)
class RegimeVerdict:
    """一次仲裁的完整結果。**唯讀**，全站唯一的 regime 真相載體。

    Attributes:
        regime:    英文 canonical，`{'bull','neutral','caution','bear','unknown'}`。
        light:     🟢 / 🟡 / 🔴 / ⬜（與 `regime` 由同一次判定產生，不可能不同步）。
        source:    哪一條分支生效（`SOURCE_*` 常數之一）。畫面可據此解釋
                   「為什麼是這個燈」，log 可據此追溯。
        defense:   外資期貨防禦訊號是否成立（給 `calc_traffic_light` 回傳沿用）。
        is_loaded: 總經是否已評估。False → `regime='unknown'`，消費端須顯示
                   「⬜ 總經未評估」而**不得**退回任何預設多空（§1）。
    """
    regime: str
    light: str
    source: str
    defense: bool = False
    is_loaded: bool = True


#: 未評估的唯一表示。消費端拿到它一律顯示 ⬜，不得走完整套判定。
UNLOADED_VERDICT: RegimeVerdict = RegimeVerdict(
    regime='unknown', light=LIGHT_UNKNOWN, source=SOURCE_UNLOADED,
    defense=False, is_loaded=False,
)


def light_for_regime(regime: Any) -> str:
    """regime → 燈號 emoji；未知 regime 一律 ⬜（不猜）。"""
    return REGIME_LIGHT.get(str(regime or '').strip().lower(), LIGHT_UNKNOWN)


def is_foreign_futures_defense(market_score: Any,
                               futures_net_lots: Any) -> bool:
    """外資期貨防禦訊號（原 `calc_traffic_light._defense`，邏輯逐字搬移）。

    成立條件（三者皆須為**已知**且成立）：
      1. 大盤評分 < `DEFENSE_MAX_MARKET_SCORE`
      2. 外資期貨淨口為負（淨空）
      3. |淨口| > `FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD`（30,000 口）

    Args:
        market_score:     `market_regime()` 的 `score`（0~6）。None → 不成立。
        futures_net_lots: 外資期貨淨口（TX 當量口，負 = 淨空）。None → 不成立。

    Returns:
        bool。

    Note:
        §1：任一輸入未取得 → 回 False，語意是「**無法確認**有大空單」，
        而不是「確認沒有大空單」。缺資料不觸發防禦，但也不會被當成安全訊號 ——
        缺失由 `calc_traffic_light` 的信心分數 / missing_sources 另行揭露。
    """
    _score = _to_float(market_score)
    _fut = _to_float(futures_net_lots)
    if _score is None or _fut is None:
        return False
    return (_score < DEFENSE_MAX_MARKET_SCORE
            and _fut < 0
            and abs(_fut) > FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD)


def arbitrate_regime(
    *,
    trend_regime: Any,
    market_score: Any,
    health: Any,
    futures_net_lots: Any = None,
    health_defense_threshold: Optional[float] = None,
    bull_min_score: Optional[float] = None,
    is_loaded: bool = True,
) -> RegimeVerdict:
    """**唯一**的大盤 regime 決策樹。全站任何 regime 判定都必須走這裡。

    決策順序（先命中先贏，對齊 `calc_traffic_light` v19.181 之前的
    if/elif 順序，**判定結果逐分支等價**）::

        0. is_loaded=False 或 health 未知     → ⬜ unknown  (unloaded)
        1. 外資期貨防禦訊號成立               → 🔴 bear     (defense:foreign_futures)
        2. health < health_defense_threshold  → 🔴 bear     (defense:health_below_threshold)
        3. trend_regime=='bull' 且            → 🟢 bull     (bull:score)
           market_score >= bull_min_score
        4. trend_regime ∈ {caution, bear}     → 🔴 bear     (bear:trend_regime)
        5. 其他                               → 🟡 neutral  (neutral:fallthrough)

    Args:
        trend_regime:  `market_regime()` 的 `regime`（趨勢面 bull/neutral/bear）。
            這是**輸入之一**，不是結論 —— 分支 1/2 會直接覆蓋它。
        market_score:  `market_regime()` 的 `score`。
        health:        總經健康分 0~100（`calc_traffic_light` 的 `health`）。
            None → 視同未評估（§1：沒有健康分就沒有結論，不猜）。
        futures_net_lots: 外資期貨淨口（負 = 淨空）。None → 分支 1 不成立。
        health_defense_threshold: 覆寫 `HEALTH_DEFENSE_THRESHOLD`（校準腳本用）。
        bull_min_score:           覆寫 `BULL_MIN_SCORE`（校準腳本用）。
        is_loaded:     caller 已知「總經根本沒評估」時傳 False。

    Returns:
        RegimeVerdict（frozen）。

    Note:
        分支 4 用的是 **`trend_regime`** 而非任何再加工的值 —— 趨勢面已明確轉空時
        直接保守，不需要健康分也跌破門檻才承認。分支 1/2 之所以排在前面，是因為
        它們代表「總經惡化凌駕技術面多頭」（§2.1：衝突時上層贏，禁止平均）。
    """
    if not is_loaded:
        return UNLOADED_VERDICT

    _health = _to_float(health)
    if _health is None:
        # health 是分支 2 的唯一依據，也是 position_throttle 的唯一輸入。
        # 拿不到就沒有結論可言 —— 誠實回 unknown，不用 trend_regime 頂替（§1）。
        return UNLOADED_VERDICT

    # 兩個門檻都由 caller 指定時**不讀檔**（`calc_traffic_light` 一律傳 ——
    # 它在 module import 時就載好了；每次呼叫再 stat 一次 json 是無謂 I/O）。
    if health_defense_threshold is None or bull_min_score is None:
        _h_default, _s_default = load_calibrated_thresholds()
    else:
        _h_default, _s_default = health_defense_threshold, bull_min_score
    _h_thr = (health_defense_threshold if health_defense_threshold is not None
              else _h_default)
    _s_thr = (bull_min_score if bull_min_score is not None else _s_default)

    _trend = str(trend_regime or '').strip().lower()
    _score = _to_float(market_score)

    # 1. 外資期貨防禦（總經惡化凌駕技術面）
    if is_foreign_futures_defense(_score, futures_net_lots):
        return RegimeVerdict('bear', LIGHT_BEAR, SOURCE_DEFENSE_FUTURES,
                             defense=True, is_loaded=True)

    # 2. 健康分跌破防禦門檻
    if _health < float(_h_thr):
        return RegimeVerdict('bear', LIGHT_BEAR, SOURCE_DEFENSE_HEALTH,
                             defense=False, is_loaded=True)

    # 3. 多頭（趨勢 bull 且評分達標）
    if _trend == 'bull' and _score is not None and _score >= float(_s_thr):
        return RegimeVerdict('bull', LIGHT_BULL, SOURCE_BULL_SCORE,
                             defense=False, is_loaded=True)

    # 4. 趨勢面已轉守/轉空
    if _trend in ('caution', 'bear'):
        return RegimeVerdict('bear', LIGHT_BEAR, SOURCE_BEAR_TREND,
                             defense=False, is_loaded=True)

    # 5. 其他 → 震盪
    return RegimeVerdict('neutral', LIGHT_NEUTRAL, SOURCE_NEUTRAL_FALLTHROUGH,
                         defense=False, is_loaded=True)
