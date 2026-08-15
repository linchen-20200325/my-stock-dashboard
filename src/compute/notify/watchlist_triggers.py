"""src/compute/notify/watchlist_triggers.py — 觀察池訊號判定（T3，L2 純函式）。

回答一個問題：**「我在追蹤的這幾檔，今天有沒有出事？」**

§8.2 layer：**L2 純函式** —— 零 I/O、零 streamlit、零 session_state。
K 線由 caller（L6 cron）抓好傳入，本模組只做判定。
（同 `src/compute/notify/__init__.py:3` 既有紀律：「無 I/O、無 streamlit、無 session_state」。）

════════════════════════════════════════════════════════════════════
為什麼是「技術性」判定 —— 而且為什麼不能沿用 risk_control 那三支
════════════════════════════════════════════════════════════════════
個股觀察池是**純代碼清單**（`gsheet_portfolio.py:60` schema 只有
`name | ticker | updated_at`，`:56-58` 註解明寫「無張數/均價」）⇒ 系統
**不知道你的成本價**。

實讀後確認 `src/compute/risk/risk_control.py` 的三支停損函式**全都以
`buy_price` 為第一參數**，一支都用不了：
  · `atr_stop_price(buy_price, atr, ...)`        `:100`
  · `stop_loss_trigger(buy_price, current_price, ...)` `:112`
  · `trailing_stop_trigger(buy_price, peak_price, ...)` `:124`

而技術性判定**本來就不該吃成本價** —— 市場不知道你買在哪。一檔股票有沒有
跌破結構，與你的進場點無關；用成本 % 當停損是行為金融學上典型的錨定偏誤。

════════════════════════════════════════════════════════════════════
三條規則（user 2026-08-14 裁示：A + B，門檻沿用既有分級）
════════════════════════════════════════════════════════════════════

**規則 1：均線跌破（穿越，非位於）**

    MA_n(t) = (1/n) · Σ_{i=0..n-1} C_(t-i)

    trigger = [ C_t < MA_n(t) ] ∧ [ C_(t-1) ≥ MA_n(t-1) ]

⚠️ 「**穿越**」而非「**位於下方**」是本模組最關鍵的設計。
若只判 `C_t < MA_n(t)`，一檔跌破後在均線下方盤整的股票會**連續數十個交易日
每天推播一次** —— 三天內使用者就會關掉通知，整套系統的價值歸零。
需要 **n+1 根** K 線才算得出（要有 t-1 的均線）。

**規則 2：技術面轉空**

直接用 `exit_signals.compute_tech_bearish(df)['bearish']`。
該函式自身已是複合判定（`exit_signals.py:119`：「含強訊號（空頭排列 /
週MACD翻負）或 ≥2 條警示」）⇒ **它自己就帶門檻**，不需要再套一層。

**規則 3：三維出場（可用時才算）**

`exit_signals.evaluate_exit_signals(tech, chip_signal, news)` 的
score（0–3）對映 `_LEVELS`（`exit_signals.py:36-41`）：
    3 → 🔴 強烈出場 ／ 2 → 🟠 建議減碼 ／ 1 → 🟡 留意觀察 ／ 0 → 🟢 訊號清淡

**觸發門檻沿用該既有分級的語意**（user 裁示：不另立新常數）——
`_LEVELS` 已把 2 定義為「建議減碼」、3 為「強烈出場」，那就是「需要你知道」
的分界；1「留意觀察」不推播。故 `EXIT_SIGNAL_ACTIONABLE_SCORE = 2`
的正當性來自既有語意，不是拍腦袋的數字（§3.3）。

⚠️ **規則 3 在 v1 通常算不到 2 分**：籌碼維度需要 `外資`/`投信` 欄，
而 cron 用的 `fetch_stock_history_1y` **不回這兩欄**；新聞維度需要 Gemini。
所以規則 1、2 才是 v1 的主力 —— 這也是為什麼**不能**只做規則 3
（只做它 = 寫了但永遠不觸發）。可評估的維度數一律回報，不假裝評過。

════════════════════════════════════════════════════════════════════
欄名陷阱（§4.1）
════════════════════════════════════════════════════════════════════
`fetch_stock_history_1y`（`picker_fetcher.py:30-34`）回傳 **大寫** 欄名
`Close / Open / High / Low / Volume`；而
  · `compute_tech_bearish` 檢查 **小寫** `'close'`（`exit_signals.py:123`）
  · `analyze_20d_chips_from_df` 檢查 **小寫** `'volume'`（`macro_compute.py:101`）
不正規化的話兩者都會**靜默回「無訊號 / 資料不足」**——
不是報錯，是安靜地什麼都不推。故 `normalize_ohlcv()` 是必經之路。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

__all__ = [
    "EXIT_SIGNAL_ACTIONABLE_SCORE",
    "TRIGGER_MA_CROSS",
    "TRIGGER_TECH_BEARISH",
    "TRIGGER_EXIT_SIGNALS",
    "TickerVerdict",
    "ScanResult",
    "normalize_ohlcv",
    "evaluate_ma_cross",
    "evaluate_ticker",
    "scan_watchlist",
]

#: 三維出場的推播分界。**沿用** `exit_signals._LEVELS` 既有語意：
#: 2 = 「🟠 建議減碼」、3 = 「🔴 強烈出場」都是需要使用者知道的狀態；
#: 1 =「🟡 留意觀察」不打擾。此值不是新發明的門檻，是既有分級的引用點。
EXIT_SIGNAL_ACTIONABLE_SCORE = 2

TRIGGER_MA_CROSS = "ma_cross"
TRIGGER_TECH_BEARISH = "tech_bearish"
TRIGGER_EXIT_SIGNALS = "exit_signals"

#: `fetch_stock_history_1y` 大寫欄 → 下游 L2 期望的小寫欄。
_COLUMN_ALIASES = {
    "Close": "close", "Open": "open", "High": "high",
    "Low": "low", "Volume": "volume",
}


def normalize_ohlcv(df):
    """把 OHLCV 欄名統一成小寫；已是小寫則原樣返回。

    §4.1：`picker_fetcher` 回大寫、`exit_signals` / `macro_compute` 要小寫。
    不做這一步，下游會**靜默**回「無訊號 / 資料不足」而不是報錯 ——
    整個觀察池會安靜地永遠不觸發。

    不修改輸入（回新物件），避免污染 caller 手上的 df。
    """
    if df is None or not hasattr(df, "columns"):
        return df
    _rename = {_k: _v for _k, _v in _COLUMN_ALIASES.items()
               if _k in df.columns and _v not in df.columns}
    return df.rename(columns=_rename) if _rename else df


@dataclass(frozen=True)
class TickerVerdict:
    """單一標的的判定結果。

    `triggers` 為空 = 今天沒事（**不是**「沒評估」——後者看 `skipped_reason`）。
    這個區分是 §1 的核心：使用者必須能分辨「安全」與「不知道」。
    """

    ticker: str
    name: str = ""
    triggers: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    data_date: str | None = None
    close: float | None = None
    evaluated_dims: int = 0
    """三維出場中實際有資料的維度數（0–3）。0 = 三維完全沒評估。"""
    exit_score: int | None = None
    exit_headline: str = ""
    skipped_reason: str | None = None
    """非 None 代表**沒能評估**（K 線不足 / 停牌 / 抓不到）。"""

    @property
    def fired(self) -> bool:
        return bool(self.triggers) and self.skipped_reason is None

    @property
    def evaluated(self) -> bool:
        return self.skipped_reason is None


def evaluate_ma_cross(df, window: int) -> dict[str, Any] | None:
    """均線**跌破穿越**判定。

    Args:
        df: 已正規化（小寫欄名）的 OHLCV，需含 `close`。
        window: 均線期數。由 caller 明確指定 —— L2 不藏設定值。

    Returns:
        `{'crossed': bool, 'ma': float, 'close': float, 'prev_close': float,
          'prev_ma': float}`；資料不足回 `None`（**不是** `crossed=False` ——
        「算不出來」與「沒跌破」是兩件事，§1）。

    需要 `window + 1` 根 K 線：判「昨天還在上面」必須有 t-1 的均線。
    """
    if df is None or "close" not in getattr(df, "columns", []):
        return None
    try:
        import pandas as _pd
        _c = _pd.to_numeric(df["close"], errors="coerce").dropna()
    except Exception:
        return None
    if len(_c) < window + 1:
        return None

    _ma = _c.rolling(window).mean()
    _ma_t, _ma_p = float(_ma.iloc[-1]), float(_ma.iloc[-2])
    _c_t, _c_p = float(_c.iloc[-1]), float(_c.iloc[-2])
    if not all(map(_finite, (_ma_t, _ma_p, _c_t, _c_p))):
        return None

    return {
        "crossed": bool(_c_t < _ma_t and _c_p >= _ma_p),
        "ma": _ma_t, "close": _c_t, "prev_close": _c_p, "prev_ma": _ma_p,
    }


def _finite(x) -> bool:
    import math
    return isinstance(x, (int, float)) and math.isfinite(x)


def _data_date(df) -> str | None:
    """取 df 最後一根 K 線的日期字串（供訊息標示資料日，判斷是否為舊資料）。"""
    try:
        _idx = df.index[-1]
        return _idx.strftime("%Y-%m-%d") if hasattr(_idx, "strftime") else str(_idx)[:10]
    except Exception:
        return None


def evaluate_ticker(
    ticker: str,
    df,
    *,
    name: str = "",
    ma_windows: Sequence[int] = (20,),
    chip_signal: str = "",
    news: Mapping[str, Any] | None = None,
    min_bars: int = 21,
) -> TickerVerdict:
    """對單一標的跑完三條規則。

    Args:
        ticker / name: 代號與名稱（名稱僅供訊息可讀性）。
        df: 原始 OHLCV（大小寫皆可，內部會 `normalize_ohlcv`）。
        ma_windows: 要檢查的均線期數。由 caller 指定（v1 傳 `(20,)`）。
        chip_signal: `analyze_20d_chips_from_df(...)['signal']`；空字串 = 未評估。
        news: `judge_news_sentiment(...)`；None = 未掃描。
        min_bars: 低於此根數視為「歷史不足」而**不評估**（§4.6 新上市）。

    Returns:
        `TickerVerdict`。**不拋例外** —— 單一檔出問題不該讓整份推播失敗，
        但也不會被靜默當成「沒事」：問題會記在 `skipped_reason` 並由
        caller 列進訊息末尾（§1）。
    """
    _t = str(ticker).strip()
    if df is None or not hasattr(df, "columns") or len(df) == 0:
        return TickerVerdict(_t, name, skipped_reason="抓不到 K 線")

    _d = normalize_ohlcv(df)
    if "close" not in _d.columns:
        return TickerVerdict(_t, name, skipped_reason="K 線缺 close 欄")
    if len(_d) < min_bars:
        return TickerVerdict(
            _t, name, skipped_reason=f"歷史不足（{len(_d)} 根 < {min_bars} 根）")

    _date = _data_date(_d)
    _triggers: list[str] = []
    _reasons: list[str] = []
    _close: float | None = None

    # ── 規則 1：均線跌破穿越 ────────────────────────────────
    for _w in ma_windows:
        _r = evaluate_ma_cross(_d, int(_w))
        if _r is None:
            continue
        _close = _r["close"]
        if _r["crossed"]:
            _triggers.append(f"{TRIGGER_MA_CROSS}:{_w}")
            _reasons.append(
                f"跌破 MA{_w}（收 {_r['close']:.2f} < MA{_w} {_r['ma']:.2f}；"
                f"前一日 {_r['prev_close']:.2f} 仍在線上）")

    # ── 規則 2：技術面轉空（函式自帶複合門檻）────────────────
    _tech: dict | None = None
    try:
        from src.compute.scoring.exit_signals import compute_tech_bearish
        _tech = compute_tech_bearish(_d)
        if _tech.get("bearish"):
            _triggers.append(TRIGGER_TECH_BEARISH)
            _rs = "、".join(_tech.get("reasons", [])[:3]) or "多項技術警示"
            _reasons.append(f"技術面轉空（{_rs}）")
    except Exception as _e:  # noqa: BLE001 — 單一維度失敗不該讓整檔判定消失
        print(f"[watchlist_triggers] {_t} compute_tech_bearish 失敗："
              f"{type(_e).__name__}: {_e}")

    # ── 規則 3：三維出場（可用時才算）─────────────────────
    # §1：把「實際評估了幾維」誠實回報。籌碼需 外資/投信 欄、新聞需 Gemini，
    # v1 兩者常缺 —— 缺了就是缺了，不可讓 score 看起來像評過三維。
    _dims = sum((_tech is not None, bool(chip_signal), news is not None))
    _score: int | None = None
    _headline = ""
    if _dims > 0:
        try:
            from src.compute.scoring.exit_signals import evaluate_exit_signals
            _ex = evaluate_exit_signals(
                tech=_tech, chip_signal=chip_signal or "", news=news)
            _score = int(_ex.get("score", 0))
            _headline = str(_ex.get("headline", ""))
            if _score >= EXIT_SIGNAL_ACTIONABLE_SCORE:
                _triggers.append(TRIGGER_EXIT_SIGNALS)
                _reasons.append(_headline)
        except Exception as _e:  # noqa: BLE001
            print(f"[watchlist_triggers] {_t} evaluate_exit_signals 失敗："
                  f"{type(_e).__name__}: {_e}")

    return TickerVerdict(
        ticker=_t, name=name,
        triggers=tuple(_triggers), reasons=tuple(_reasons),
        data_date=_date, close=_close,
        evaluated_dims=_dims, exit_score=_score, exit_headline=_headline,
    )


@dataclass(frozen=True)
class ScanResult:
    """整份觀察池的掃描結果，供訊息層直接取用。"""

    verdicts: tuple[TickerVerdict, ...] = ()
    data_dates: tuple[str, ...] = field(default=())

    @property
    def fired(self) -> tuple[TickerVerdict, ...]:
        return tuple(v for v in self.verdicts if v.fired)

    @property
    def skipped(self) -> tuple[TickerVerdict, ...]:
        return tuple(v for v in self.verdicts if not v.evaluated)

    @property
    def n_evaluated(self) -> int:
        return sum(1 for v in self.verdicts if v.evaluated)

    @property
    def all_skipped(self) -> bool:
        """全部都沒評估成功。

        §1：此時**絕不可**推「今日無觸發」—— 那會把「全部抓不到」說成
        「全部安全」，是最危險的假訊號。caller 必須改推診斷訊息。
        """
        return bool(self.verdicts) and self.n_evaluated == 0


def scan_watchlist(verdicts: Sequence[TickerVerdict]) -> ScanResult:
    """彙整逐檔判定。純聚合，不重算。"""
    _v = tuple(verdicts)
    _dates = tuple(sorted({v.data_date for v in _v if v.data_date}))
    return ScanResult(verdicts=_v, data_dates=_dates)
