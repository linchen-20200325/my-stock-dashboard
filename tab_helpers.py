"""跨 tab_*.py 共用的純函式 — Phase 7A 抽純函式（2026-05-16）

零 Streamlit / Plotly 依賴，無 side effect。
從 tab_stock.py / tab_stock_grp.py / tab_macro.py 內部抽出的重複工具。

設計原則：
- pure function：相同輸入恆等輸出
- 防呆優先：所有 helper 對 None / NaN / 缺欄位皆有 fallback
- 易測：對應 tests/test_tab_helpers.py 完整 coverage
"""
from __future__ import annotations

import re
from typing import Any, Optional

import pandas as pd
from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW

_PCT_RE = re.compile(r'(-?\d+(?:\.\d+)?)\s*%')


def parse_cash_flow_ratio(value: Any, threshold: float, strict: bool = False) -> Optional[bool]:
    """解析含百分比字串並對照門檻 — 取代 tab_stock._r110_ok_a / tab_stock_grp._r110_ok_b。

    對應 financial_health_engine 的 Rule 100/100/10 三項檢核
    （A: Cash_Flow_Ratio > 100% 嚴格 / B: Cash_Flow_Adequacy ≥ 100% / C: Cash_Reinvestment > 10% 嚴格）。

    Args:
        value: 含 "%" 的字串、None、或 "N/A"
        threshold: 比較門檻（數值，單位 %）
        strict: True → 嚴格 `>`；False → `>=`

    Returns:
        True / False / None（值缺失或無法解析）
    """
    s = str(value or '')
    if not s or 'N/A' in s:
        return None
    m = _PCT_RE.search(s)
    if not m:
        return None
    v = float(m.group(1))
    return (v > threshold) if strict else (v >= threshold)


def format_condition_emoji(value: Optional[bool]) -> str:
    """三態 bool → emoji — 取代 tab_stock._tk2 / tab_stock_grp._tk。

    True → ✅、False → ❌、None / 其他 → ⚪。
    """
    if value is True:
        return '✅'
    if value is False:
        return '❌'
    return '⚪'


def safe_get(value: Any) -> Any:
    """過濾 None / NaN，其餘原樣返回 — 取代 tab_macro._v。

    用於從 pandas Series / dict 取欄位後的防呆，
    避免 NaN 進入下游條件判斷造成 silent bug。
    """
    try:
        if value is None or pd.isna(value):
            return None
    except (TypeError, ValueError):
        return None
    return value


def final_recommendation(row: dict, score_map: dict) -> tuple[str, str]:
    """個股最終綜合建議 — 取代 tab_stock_grp._final_rec closure。

    四項加分（健康度 + 多因子總分 + 估值帶位 + 趨勢）合計：
      pts ≥ 7：🟢 積極 / pts ≥ 4：🟡 觀察 / 其餘：🔴 等待。

    Args:
        row: 至少含 'stock_id'，可選 '_health' / '_val' / '_trend'
        score_map: {stock_id → {'total': mf_score}} 多因子總分對照

    Returns:
        (label, color_hex)
    """
    health   = row.get('_health', 0)
    val      = row.get('_val', '')
    trend    = row.get('_trend', '')
    mf_total = score_map.get(row['stock_id'], {}).get('total', 0)
    # v18.214 K7：走 shared/health_thresholds SSOT 閾值常數
    from shared.health_thresholds import HEALTH_GRADE_A_MIN, HEALTH_GRADE_B_MIN
    pts = 0
    if health >= HEALTH_GRADE_A_MIN:
        pts += 3
    elif health >= HEALTH_GRADE_B_MIN:
        pts += 1
    if mf_total >= 75:
        pts += 3
    elif mf_total >= 55:
        pts += 1
    if '便宜' in val:
        pts += 2
    elif '合理' in val:
        pts += 1
    if '多頭' in trend:
        pts += 1
    if pts >= 7:
        return '🟢 積極', TRAFFIC_GREEN
    if pts >= 4:
        return '🟡 觀察', TRAFFIC_YELLOW
    return '🔴 等待', TRAFFIC_RED


def safe_ma(df: pd.DataFrame, n: int) -> float:
    """取最新 MA{n} — 取代 tab_stock._safe_ma。

    優先讀 df['MA{n}'] 既有欄位；缺欄位但資料足 → 即時 rolling；
    資料不足 → 退回 close 平均（最保守 fallback）。

    Args:
        df: 至少有 'close' 欄位
        n: 均線天數（5/20/60/120/240）

    Returns:
        float — 最後一根的 MA 值
    """
    col = f'MA{n}'
    if col in df.columns:
        return float(df[col].iloc[-1])
    if len(df) >= n:
        return float(df['close'].tail(n).mean())
    return float(df['close'].mean())


def classify_stock_status_lamp(health_score: float | None,
                                 trend_label: str | None,
                                 bias_pct: float | None,
                                 vol_ratio: float | None,
                                 valuation_label: str | None = None) -> str:
    """v18.336 PR-H4:操作狀態燈 🔵🟡🟠⚪ SSOT(個股 + 個股組合 Tab 共用)。

    原 tab_stock_grp.py:285-305 inline 抽出。判定邏輯依四維度合議:
    - 🔵 加碼:健康 A 級(≥HEALTH_GRADE_A_MIN)+ 多頭排列 + 量縮(vol < GRP_VOL_SHRINK_RATIO)+ 近 20MA(|bias| < GRP_NEAR_MA20_BIAS_PCT)
    - 🟡 警示:MA20 乖離 > GRP_BIAS_OVERHEAT_WARN_PCT(短線漲多)
    - 🟠 減碼:估值「昂貴 / 超貴」(357 殖利率分級結論)
    - ⚪ 中性:其餘 / 資料不足

    Args:
        health_score: 6 因子健康評分 0-100
        trend_label: 趨勢標籤(`📈 多頭` / `📉 空頭` / `📊 多箱` / `📊 空箱`)— 內含「多頭」字串即過
        bias_pct: MA20 乖離率 %(可為負)
        vol_ratio: 當日量 / 20 日均量(0.7 = 量縮 30%)
        valuation_label: 估值結論(含「昂貴」/「超貴」即觸發 🟠)

    Returns:
        '🔵 加碼' / '🟡 警示' / '🟠 減碼' / '⚪'(資料不足或中性)

    SSOT 政策:個股 + 個股組合 Tab 共用。閾值來自 shared.signal_thresholds。
    """
    from shared.health_thresholds import HEALTH_GRADE_A_MIN
    from shared.signal_thresholds import (
        GRP_BIAS_OVERHEAT_WARN_PCT,
        GRP_NEAR_MA20_BIAS_PCT,
        GRP_VOL_SHRINK_RATIO,
    )
    # 🔵 加碼:四維度合議
    if (health_score is not None and health_score >= HEALTH_GRADE_A_MIN
            and trend_label and '多頭' in str(trend_label)
            and vol_ratio is not None and vol_ratio < GRP_VOL_SHRINK_RATIO
            and bias_pct is not None and abs(bias_pct) < GRP_NEAR_MA20_BIAS_PCT):
        return '🔵 加碼'
    # 🟡 警示:乖離過熱
    if bias_pct is not None and bias_pct > GRP_BIAS_OVERHEAT_WARN_PCT:
        return '🟡 警示'
    # 🟠 減碼:估值偏貴
    if valuation_label and ('昂貴' in str(valuation_label) or '超貴' in str(valuation_label)):
        return '🟠 減碼'
    return '⚪'


def compute_stop_levels(price: float | None) -> dict | None:
    """v18.336 PR-H4:停利停損價位 SSOT(個股 Tab 顯著視覺化 + 組合 Tab 可擴充)。

    依當前價計算 T1 停利 / T2 停利 / Default 停損三個價位。
    閾值來自 shared.signal_thresholds.STOP_PROFIT_T1/T2_PCT + STOP_LOSS_DEFAULT_PCT(PR-C 已抽 SSOT)。

    Args:
        price: 當前收盤價(>0)

    Returns:
        dict {
          'stop_profit_t1': float,    # price × (1 + T1%/100)
          'stop_profit_t2': float,    # price × (1 + T2%/100)
          'stop_loss_default': float,  # price × (1 - LOSS%/100)
          't1_pct': float / 't2_pct' / 'loss_pct',  # 對應 %(供 label 顯示)
        }
        price ≤ 0 或 None → None

    SSOT 政策:停利停損計算統一,任何 Tab 顯示進場後管理價位均呼叫本函式。
    原 tab_stock.py:591-602 inline,本 PR 抽出為純函式。
    """
    from shared.signal_thresholds import (
        STOP_LOSS_DEFAULT_PCT,
        STOP_PROFIT_T1_PCT,
        STOP_PROFIT_T2_PCT,
    )
    if not price or price <= 0:
        return None
    return {
        'stop_profit_t1': price * (1 + STOP_PROFIT_T1_PCT / 100),
        'stop_profit_t2': price * (1 + STOP_PROFIT_T2_PCT / 100),
        'stop_loss_default': price * (1 - STOP_LOSS_DEFAULT_PCT / 100),
        't1_pct': STOP_PROFIT_T1_PCT,
        't2_pct': STOP_PROFIT_T2_PCT,
        'loss_pct': STOP_LOSS_DEFAULT_PCT,
    }


def classify_bias_zone(bias_pct: float | None) -> tuple[str, str]:
    """v18.336 PR-H4:月線/年線乖離分層 SSOT(對應 STOCK_BIAS_* 三層)。

    Args:
        bias_pct: 乖離率 %(可正可負)

    Returns:
        (label, color):
        - bias < -OVERHEAT(-20%)  → '🟢 深度負乖離(布局區)' / green
        - bias > +OVERHEAT(+20%)  → '🔴 過熱正乖離(分批出場)' / red
        - |bias| > MILD(15%)       → '🟠 中度乖離(注意)' / yellow
        - 其他                       → '⚪ 中性區' / yellow

    SSOT 政策:閾值 STOCK_BIAS_DEEP_DEVIATION_PCT / STOCK_BIAS_OVERHEAT_PCT /
    STOCK_BIAS_MILD_DEVIATION_PCT 已在 shared.signal_thresholds(PR-F U-13 已抽)。
    本函式封裝判斷層,個股 Tab 月線/年線乖離視覺化共用。
    """
    from shared.signal_thresholds import (
        STOCK_BIAS_DEEP_DEVIATION_PCT,
        STOCK_BIAS_MILD_DEVIATION_PCT,
        STOCK_BIAS_OVERHEAT_PCT,
    )
    if bias_pct is None:
        return '⚪ 無資料', TRAFFIC_YELLOW
    if bias_pct < -STOCK_BIAS_DEEP_DEVIATION_PCT:
        return f'🟢 深度負乖離 ({bias_pct:+.1f}%,布局區)', TRAFFIC_GREEN
    if bias_pct > STOCK_BIAS_OVERHEAT_PCT:
        return f'🔴 過熱正乖離 ({bias_pct:+.1f}%,分批出場)', TRAFFIC_RED
    if abs(bias_pct) > STOCK_BIAS_MILD_DEVIATION_PCT:
        return f'🟠 中度乖離 ({bias_pct:+.1f}%,注意)', TRAFFIC_YELLOW
    return f'⚪ 中性區 ({bias_pct:+.1f}%)', TRAFFIC_YELLOW


def classify_trend_4tier(price: float, ma20: float | None,
                          ma_long: float | None) -> tuple[str, str]:
    """v18.328 PR-C P1:4 段趨勢判定 SSOT(個股 Tab + 組合 Tab 共用)。

    4 段邏輯(price = current, ma20 / ma_long = 兩條均線):
    - price > ma20 > ma_long  → 多頭(MA 多頭排列)
    - price < ma20 < ma_long  → 空頭(MA 空頭排列)
    - price > ma_long (但非多頭排列) → 多箱(站上長均但短均未多頭)
    - 其他 → 空箱

    Args:
        price: 當前收盤價
        ma20: 短均線(20 日)。None → 回('⚪無資料', neutral color)
        ma_long: 長均線(預設 MA100,組合 + 個股 K 線註解皆用)。None → 同上

    Returns:
        (label_str, color_hex):label 帶 emoji,color 對應 traffic color

    SSOT 政策:本函式統一兩 Tab 的 4 段趨勢判定。原違憲:
    - tab_stock.py:1426 inline MA20/MA100 4 段
    - tab_stock_grp.py:231 inline MA20/MA100 4 段
    - 兩處邏輯完全相同但 inline 各自實作。
    """
    if not (ma20 and ma_long and price > 0):
        return '⚪無資料', TRAFFIC_YELLOW
    if price > ma20 > ma_long:
        return '📈 多頭', TRAFFIC_GREEN
    if price < ma20 < ma_long:
        return '📉 空頭', TRAFFIC_RED
    if price > ma_long:
        return '📊 多箱', TRAFFIC_YELLOW
    return '📊 空箱', TRAFFIC_YELLOW
