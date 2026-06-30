"""shared/calc_helpers.py — 通用計算 helper(L0,純函式)。

A4 v18.384 深層拔毒:統一散落 3 處的 `series.pct_change(N) * 100.0` pattern。
"""
from __future__ import annotations


def pct_change_yoy(series, periods: int = 12, multiplier: float = 100.0):
    """通用 pct_change × multiplier(預設 12 月 YoY × 100 = %)。

    參數:
        series: pd.Series(月頻 → periods=12 ≡ YoY;日頻 → periods=20 ≡ 20-day 跌幅)
        periods: pct_change 期數,預設 12(月頻 YoY)
        multiplier: 結果乘數,預設 100.0(% 表示)

    Caller(3 處):
    - src/compute/macro/macro_helpers.py:860 M2 YoY(月頻 12)
    - src/compute/scoring/scoring_engine.py:446 revenue YoY(月頻 12)
    - src/compute/macro/macro_signal_lookback_tw.py:191 TWII 20D 跌幅(日頻 20)
    """
    return series.pct_change(periods) * multiplier


def daily_return_rolling_std(close, window: int = 20):
    """日報酬率波動率(`close.pct_change().rolling(N).std()`)。

    E-2 v18.387 抽自 scoring_engine.py:122,240 inline pattern。

    參數:
        close: pd.Series 收盤價(日頻)
        window: rolling 視窗,預設 20

    回傳:pd.Series(日報酬率 N-day std);caller 通常取 `.iloc[-1]`。
    """
    return close.pct_change().rolling(window).std()


def calc_bias_pct(price, ma, *, decimals: int | None = None):
    """乖離率 = (price - ma) / ma × 100  (%);scalar 場景 SSOT。

    C1 v18.401 收斂:tab_stock.py 4 處 + etf_calc.py 2 處 + etf_helpers.py 2 處
    重寫 `(price - ma) / ma * 100`(同公式,fall-loud guard 不一致)。

    參數:
        price: float | None 當前價(scalar)
        ma:    float | None 移動平均(scalar)
        decimals: int | None 四捨五入位數;None 不 round

    Returns:
        float 乖離率 %;若 price/ma 為 None 或 ma <= 0 → 回 None(non-fabricating)

    範例:
        calc_bias_pct(110, 100)             # 10.0
        calc_bias_pct(95.3, 100, decimals=1)  # -4.7
        calc_bias_pct(100, 0)               # None(避免 ZeroDivisionError + 不捏造)
        calc_bias_pct(None, 100)            # None
    """
    if price is None or ma is None:
        return None
    try:
        _ma = float(ma)
        _p = float(price)
    except (TypeError, ValueError):
        return None
    if _ma <= 0:
        return None
    _bias = (_p - _ma) / _ma * 100.0
    return round(_bias, decimals) if decimals is not None else _bias


def calc_bias_pct_series(price, ma):
    """乖離率 series 版 SSOT = (price - ma) / ma × 100  (%);向量化。

    v18.436 #23:補 calc_bias_pct 的 series 缺口(原 scalar-only 無法覆蓋
    etf_render.py:237 `(close - ma20) / ma20 * 100` 等 Series 路徑)。

    與 scalar 版同公式 + 同 fail-loud 語意:ma<=0 的位置回 NaN(不捏造、不 ÷0),
    而非 raise — 因 series 通常含開頭 rolling NaN(ma 尚未成形),逐點 guard 才合理。

    參數:
        price: pd.Series 當前價序列
        ma:    pd.Series 移動平均序列(index 對齊 price)

    回傳:
        pd.Series 乖離率 %;ma<=0 或 NaN 的位置為 NaN。
    """
    # ma<=0(含 NaN 比較為 False)→ 該點設 NaN,避免 ÷0 / 捏造
    _safe_ma = ma.where(ma > 0)
    return (price - _safe_ma) / _safe_ma * 100.0
