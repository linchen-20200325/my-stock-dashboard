"""src/services/market_twii_view_service.py — 📊 市場頁圖 A（台股指數）的薄 L3 讀取層。

單一職責：把 L1 `macro_cache_reader.load_twii_close()` 的 **Series + `.attrs`**（`is_stale`／`stale_reason`／`as_of`／
`age_days`／`upstream_error`）原樣帶到 L5。

為什麼不用 `macro_v2_service.get_twii_ohlc()` / `get_chart_series()`：兩者回傳 list／dict，**不帶 attrs**
（A 規格 §4.1.2：「圖 A 應走 `load_twii_close` 的 attrs，否則違反 §2.4『過期須帶 is_stale』」）。
L5 不得 import L1（CLAUDE.md §8.2 硬規則 4）⇒ 由本層包一層；**本層不改 L1、不新增資料源、不算任何指標**。

§1 Fail Loud：
- 讀不到（檔不存在／壞檔／缺欄／空）→ `ok=False` 並寫明原因；⛔ 不回空殼讓畫面以為「有資料但沒東西」。
- attrs 缺（新鮮度判定本身壞掉）→ `is_stale=None`（⬜ 未判定），⛔ 不當成「新鮮」。
- 不快取（本機 parquet 讀取，毫秒級）⇒ 不存在「失敗被凍成 TTL 那麼久」的問題（v3 §02 第 3 點 a）。

窗口天數沒有預設值：「畫幾天」是畫面決策（屬 L5，同 `macro_v2_service.get_twii_ohlc` 的作法），避免兩處各有一份。
"""
from __future__ import annotations

from dataclasses import dataclass

#: 資料來源說明（給「查看依據」用；與 A 規格 §4.1.2 圖 A 來源列同一個說法）。
# 內部對照：data_cache/twii_ohlcv.parquet（Yahoo:^TWII:chart，每日 cron 更新）；畫面上只寫白話。
TWII_SOURCE_TEXT: str = "本地加權指數歷史快取（來源 Yahoo，每日更新）"


@dataclass(frozen=True)
class TwiiTrendView:
    """加權指數收盤序列＋新鮮度事實（唯讀）。

    Attributes:
        ok: 有可畫的序列。
        xs: ISO 日期（升序），與 `close` 等長。
        close: 收盤價（已 dropna，⛔ 不補值）。
        n_available: 快取檔裡全部可用的列數（窗口之前）。
        as_of: 最後一筆資料日（ISO）；`ok=False` → None。
        is_stale: True／False；None ＝ 新鮮度沒判定出來（⬜）。
        stale_reason: 過期原因（原樣轉述 L1）；沒有則 ""。
        age_days: 距今天數（L1 判定）；None ＝ 未提供。
        upstream_error: 上游最後一次錯誤（`metadata.last_error`，原樣轉述）；沒有則 ""。
        error: `ok=False` 時的原因；`ok=True` 則 ""。
        failed: True ＝ 讀取時丟了**例外**（系統真出錯，L5 可標紅）；False 的 `ok=False` ＝ 檔不存在／壞檔／缺欄／空
            （「讀不到」，L5 標灰）。v3 §02 灰紅分離。
        source: 資料來源說明。
    """

    ok: bool
    xs: tuple[str, ...] = ()
    close: tuple[float, ...] = ()
    n_available: int = 0
    as_of: str | None = None
    is_stale: bool | None = None
    stale_reason: str = ""
    age_days: int | None = None
    upstream_error: str = ""
    error: str = ""
    failed: bool = False
    source: str = TWII_SOURCE_TEXT


def _iso(v) -> str | None:
    """日期／Timestamp／字串 → 'YYYY-MM-DD'；None／空 → None（⛔ 不用今天代替）。"""
    if v is None:
        return None
    _s = str(v).strip()
    return _s[:10] if _s else None


def get_twii_trend_view(n_trading_days: int) -> TwiiTrendView:
    """加權指數最近 `n_trading_days` 個交易日的收盤＋新鮮度。

    Args:
        n_trading_days: 取尾端幾列（parquet 每一列就是一個交易日）；< 1 → `ValueError`（⛔ 不默默回空）。
    """
    if n_trading_days < 1:
        raise ValueError(f"n_trading_days 必須 ≥ 1，收到 {n_trading_days!r}")
    try:
        from src.data.macro.macro_cache_reader import load_twii_close
        _s = load_twii_close()
    except Exception as _e:  # noqa: BLE001 — 讀不到就講出來（§1），由 L5 決定灰／紅
        print(f"[market_twii_view_service] load_twii_close 失敗：{_e!r}")
        return TwiiTrendView(ok=False, failed=True, error=f"{type(_e).__name__}: {_e}")
    if _s is None or len(_s) == 0:
        return TwiiTrendView(ok=False, error="加權指數歷史快取讀不到（檔案不存在、壞檔、缺欄或內容為空）")
    _attrs = getattr(_s, "attrs", {}) or {}
    _tail = _s.tail(n_trading_days)
    _is_stale = _attrs.get("is_stale")
    _age = _attrs.get("age_days")
    return TwiiTrendView(
        ok=True,
        xs=tuple(_iso(_i) or "" for _i in _tail.index),
        close=tuple(float(_v) for _v in _tail.values),
        n_available=int(len(_s)),
        as_of=_iso(_attrs.get("as_of")) or _iso(_tail.index[-1]),
        is_stale=(bool(_is_stale) if _is_stale is not None else None),
        stale_reason=str(_attrs.get("stale_reason") or ""),
        age_days=(int(_age) if isinstance(_age, (int, float)) and not isinstance(_age, bool) else None),
        upstream_error=str(_attrs.get("upstream_error") or ""),
    )
