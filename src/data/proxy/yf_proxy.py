"""v18.209 K5：yfinance 共用 cached + proxy wrapper（解 Cloud IP 403 風險）。

Phase 1 audit 找到 8+ 處 `yf.Ticker()` 直呼，deep check 後確認 3 處真未 cache：
  - app.py:363 (fetch_dividend_data)
  - tab_stock_picker.py:237 (_check_one_stock, in loop)
  - daily_checklist.py:487 (fetch_single, in loop)

Streamlit Cloud 海外 IP 常被 Yahoo 403/rate-limit；既有 NAS Squid Proxy 走家用台灣 IP
可繞過。但 caller 各自寫一份「env backup → set proxy → call → restore」boilerplate
易漏接。本模組提供：
  - cached_history(ticker, period): @st.cache_data(ttl=TTL_1HOUR) 包 yf.Ticker.history
  - cached_dividends(ticker): @st.cache_data(ttl=TTL_1HOUR) 包 yf.Ticker.dividends
proxy env 由模組內 try/finally 統一處理，caller 零樣板。
（兩者自 Q5-r2-r3／D2-f4 起皆「只快取成功」：快取在內層 `_cached_*_cached`，拋例外不入快取、
外層以 `shared.fail_cooldown` 退避；公開名稱與 `.clear()` 不變。D2-f16 起 K 線那支另把 yfinance
**吞成空表的網路錯誤**也辨認成失敗（見 `_history_or_raise`），並加掛 `cached_history.with_status`。）

設計：純函式 wrapper + st.cache_data；caller 用 from src.data.proxy import ... 即可。
"""
from __future__ import annotations

import os as _os
from contextlib import contextmanager

import pandas as pd
# §8.2.A EX-CACHE-1:條件 import streamlit + 無 UI 呼叫 fallback。
# 本檔僅用 @st.cache_data 包 yfinance call,無真 UI 呼叫。
try:
    import streamlit as st
except ImportError:
    class _NoOpST:
        @staticmethod
        def cache_data(*args, **kwargs):
            if args and callable(args[0]):
                return args[0]
            return lambda f: f
        cache_resource = cache_data
        secrets: dict = {}
    st = _NoOpST()  # noqa

from shared.ttls import TTL_1HOUR
from shared.fail_cooldown import FailCooldown as _FailCooldown, NO_HIT as _FC_NO_HIT


_PROXY_ENV_KEYS = ("HTTPS_PROXY", "HTTP_PROXY", "https_proxy", "http_proxy")


@contextmanager
def _proxy_env():
    """臨時設 NAS Squid Proxy 到 env vars（finally 自動還原，異常安全）。

    從 tw_stock_data_fetcher._load_proxy_config 取 proxy URL；無 proxy 時不動 env。
    """
    _purl = None
    try:
        from src.data.stock import _load_proxy_config
        _cfg = _load_proxy_config() or {}
        _purl = _cfg.get("https") or _cfg.get("http")
    except Exception:
        _purl = None
    _backup = {k: _os.environ.get(k) for k in _PROXY_ENV_KEYS}
    try:
        if _purl:
            for k in _PROXY_ENV_KEYS:
                _os.environ[k] = _purl
        yield
    finally:
        for k, v in _backup.items():
            if v is None:
                _os.environ.pop(k, None)
            else:
                _os.environ[k] = v


#: D2-f16：yfinance 在 `history(raise_errors=True)` 時用來回報「上游有回應、但這個代碼／區間
#: **沒有資料**」的例外型別名（`yfinance.exceptions`；0.2.39 起才有型別，版本沒有的名字略過）。
#: 對照 0.2.36～1.7.0 各版 `history()` 原始碼：無時區（疑似下市）＝`YFTzMissingError`、
#: 無價格／Yahoo 回報錯誤＝`YFPricesMissingError`（0.2.39～0.2.41 另有 `YFChartError`）、
#: 區間不合法＝`YFInvalidPeriodError`；前兩者皆是 `YFTickerMissingError` 的子類別。
_YF_NO_DATA_ERROR_NAMES = ("YFTickerMissingError", "YFTzMissingError", "YFPricesMissingError",
                           "YFChartError", "YFInvalidPeriodError")


def _yf_no_data_exc_types() -> tuple:
    """已安裝的 yfinance 有的「沒有資料」例外型別（見 `_YF_NO_DATA_ERROR_NAMES`）。"""
    try:
        from yfinance import exceptions as _yfe
    except Exception:  # noqa: BLE001 — 沒有這個模組 → 只剩裸 Exception 那條規則
        return ()
    return tuple(_c for _c in (getattr(_yfe, _n, None) for _n in _YF_NO_DATA_ERROR_NAMES)
                 if isinstance(_c, type) and issubclass(_c, Exception))


def _is_yf_no_data(exc: BaseException) -> bool:
    """`exc` 是 yfinance 自己回報的「沒有資料」（→ 同修前、照舊快取），而不是抓取失敗？（D2-f16）

    · 429（`YFRateLimitError`，0.2.52 起）一律**不是** —— 確定的抓取失敗（防日後型別階層變動）。
    · 型別**恰為** `Exception`：0.2.36～0.2.38 還沒有型別，`history(raise_errors=True)` 把「沒資料」
      一律拋成裸 `Exception("{ticker}: {原因}")`；網路／代理錯誤則是原樣往上拋、帶自己的型別
      （requests／curl_cffi 例外），不會是裸 `Exception`。0.2.x 全系列另有一處也拋裸 `Exception`：
      還原權息（auto_adjust）失敗 —— 同樣落在這一類（見 `_history_or_raise` 末段）。
    · 其餘：`_yf_no_data_exc_types()` 的實例。
    """
    try:
        from yfinance.exceptions import YFRateLimitError as _rate_limited
    except Exception:  # noqa: BLE001 — 0.2.52 之前沒有這個型別
        _rate_limited = None
    if _rate_limited is not None and isinstance(exc, _rate_limited):
        return False
    if type(exc) is Exception:
        return True
    _types = _yf_no_data_exc_types()
    return bool(_types) and isinstance(exc, _types)


def _history_or_raise(tk, ticker: str, period: str):
    """`tk.history(period=period)`，但**抓取失敗一律以例外浮出**（D2-f16 2026-09-28）。

    修前的破口：yfinance `history()` 預設（1.x ＝ `hide_exceptions=True`；0.2.x ＝
    `raise_errors=False`）把抓取階段的例外**吞掉**、回一張帶欄位的空表 —— 只有 429
    （`YFRateLimitError`，0.2.52 起）會往上拋；時區未快取時例外才可能從時區查詢那段拋出。
    所以「時區已快取 ＋ 網路／代理斷線」回的空表與「這檔真的沒資料」長得一模一樣，被快取層
    照舊快取 1 小時。`raise_errors=True`（0.2.36～1.7.0 各版 `history()` 皆有此參數，2026-09-28
    逐版原始碼查證；1.x 呼叫時會發 `DeprecationWarning`、建議改用全域設定，參數本身仍有效）讓兩者分開：

    · 回傳 DataFrame（含空表）→ 原樣回傳（成功路徑：內容與修前那種呼叫回的相同）；
    · yfinance 自己回報「沒有資料」（`_is_yf_no_data`）→ 回 None ＝ 修前那張空表的同一條路
      （快取層回 `pd.DataFrame()`、照舊快取）；
    · 其他例外（網路／代理錯誤、逾時、429、Yahoo 維護頁、回應不是 JSON…）→ **原樣往上拋**
      （快取層不快取，外層冷卻）。

    相容防線（兩者都退回**修前呼叫**：分不出失敗與沒資料 → 照舊，不會比修前差）：
    · 日後版本移除 `raise_errors`（`TypeError` 且訊息提到它）→ 改用修前呼叫；
    · `DeprecationWarning` 被設定成例外（`-W error`；1.x 在發出 K 線請求前就警告）→ 同上。
    已知沒有照修前的一條 —— 還原權息（auto_adjust）失敗（修前回的是**未還原**的價格），修後依版本不同：
    0.2.36～0.2.66 拋裸 `Exception` → 歸「沒資料」（回空表、照舊快取）；1.0～1.7.0 原樣拋出原例外
    → 失敗（不入快取、冷卻）。各版 `parse_quotes` 恆補 `Adj Close`，該路徑實務上到不了。
    （2026-09-29 更正：前一版此處寫成不分版本的「會拋出」，0.2.x 並非如此。）
    """
    try:
        return tk.history(period=period, raise_errors=True)
    except TypeError as _e:
        if "raise_errors" not in str(_e):
            raise
        return tk.history(period=period)
    except DeprecationWarning:
        return tk.history(period=period)
    except Exception as _e:
        if not _is_yf_no_data(_e):
            raise
        print(f"[yf_proxy.history] {ticker}: 無資料（{type(_e).__name__}: {_e}）")
        return None


#: K 線快取的鍵數上限 —— 成功快取（`_cached_history_cached` 的 `max_entries`）與失敗冷卻
#: （`_history_fail_cooldown`）共用這一個值（批 D3d N1，2026-09-29）。值 200 ＝ 修前掛在快取層上的
#: inline `max_entries=200`（原值不變，只是具名）。為何兩者必須一致：D2-f16 之後，網路／代理錯誤、
#: 維護頁、非 JSON 回應改走失敗冷卻；修前這些被當成「沒資料」存進成功快取（上限 200）。冷卻表若沿用
#: `shared.fail_cooldown.FAIL_COOLDOWN_MAX_ENTRIES`（64），同一冷卻期內失敗鍵超過 64 個時會一邊記、
#: 一邊逐出最舊的，下一輪每一鍵都重打上游（實例：RS 掃描、前進式驗證對帳逐檔＋`.TWO` 備援）。
_HISTORY_CACHE_MAX_ENTRIES: int = 200


@st.cache_data(ttl=TTL_1HOUR, max_entries=_HISTORY_CACHE_MAX_ENTRIES, show_spinner=False)
def _cached_history_cached(ticker: str, period: str = "1y") -> pd.DataFrame:
    """`cached_history()` 的快取層。**拋例外一律往上拋**（D2-f4 2026-09-28，同
    `_cached_dividends_cached`；§1.A-3(a)「只快取成功結果」；st.cache_data 不快取例外）。
    成功與「真的沒資料（回 None／空表）」兩條路徑、TTL、max_entries 同修前（照舊快取）。
    D2-f16（2026-09-28）：經 `_history_or_raise` 呼叫 —— yfinance 吞成空表的網路錯誤也往上拋。"""
    import yfinance as yf
    with _proxy_env():
        _df = _history_or_raise(yf.Ticker(ticker), ticker, period)
    if _df is None or _df.empty:
        return pd.DataFrame()
    return _df


#: D2-f4：K 線失敗退避（§1.A-3(b)）—— 冷卻期內同一 (ticker, period) 不重打 Yahoo，回同一份空表。
#: 鍵數上限＝成功快取的上限（批 D3d N1，理由見 `_HISTORY_CACHE_MAX_ENTRIES`）；冷卻秒數不變。
_history_fail_cooldown = _FailCooldown(max_entries=_HISTORY_CACHE_MAX_ENTRIES)


def _cached_history_with_status(ticker: str, period: str = "1y") -> tuple[pd.DataFrame, bool]:
    """(K 線, 這一份是不是**確定抓取失敗**)。**本函式不快取**；快取在 `_cached_history_cached`。

    第 1 項與 `cached_history(ticker, period)` 回的逐字相同。第 2 項為 True ＝ 本次（或冷卻期內
    記下的那次）快取層拋了例外 —— 給 L1 `daily_data_fetchers.fetch_single` 判斷它自己那層的
    None 能不能入快取（D2-f15；同一次呼叫取得，不必事後查退避表，沒有競態）。
    """
    _key = (ticker, period)
    _hit, _gen = _history_fail_cooldown.begin(_key)
    if _hit is not _FC_NO_HIT:
        return _hit, True
    try:
        _df = _cached_history_cached(ticker, period=period)
    except Exception as _e:
        print(f"[yf_proxy.history] {ticker}: {type(_e).__name__}: {_e}")
        return _history_fail_cooldown.fail(_key, _gen, pd.DataFrame()), True
    _history_fail_cooldown.success(_key)
    return _df, False


def cached_history(ticker: str, period: str = "1y") -> pd.DataFrame:
    """yfinance Ticker.history with NAS proxy + 1h cache（**只快取成功**）。

    Args:
        ticker: yfinance 標的代碼，例 "2330.TW"
        period: "5d"/"1mo"/"3mo"/"1y"/"5y"/"max"

    Returns:
        pd.DataFrame；抓不到回空 DataFrame（不爆例外）。回傳內容同修前（失敗也是無旗標的空表）。

    D2-f4（2026-09-28）：修前 yfinance **拋例外**（例：429 `YFRateLimitError`）時回的空表被
    快取 1 小時 —— Yahoo 恢復後同參數仍回空表。現在拋例外那一種**不入快取**；失敗後
    `shared.fail_cooldown.FAIL_COOLDOWN_SEC` 秒內同一 (ticker, period) 不重抓，回同一份空表；
    成功一次即解除。`.clear()` 同清快取與退避紀錄。
    D2-f16（2026-09-28）：**失敗 vs 真的沒資料的判準**改由 `_history_or_raise` 決定 —— yfinance
    吞掉的網路／代理錯誤（修前被當成「沒資料」快取 1 小時）也算失敗；yfinance 自己回報的
    「沒有資料」（疑似下市、查無價格、區間不合法）與「沒拋、只回 None／空表」照舊快取。
    `.with_status(ticker, period)` 見 `_cached_history_with_status`。
    """
    return _cached_history_with_status(ticker, period)[0]


def _clear_cached_history() -> None:
    getattr(_cached_history_cached, "clear", lambda: None)()
    _history_fail_cooldown.clear()


cached_history.clear = _clear_cached_history
cached_history.with_status = _cached_history_with_status


#: `cached_dividends()` **拋例外**時，回傳的空 Series 在 `attrs` 裡帶的鍵（值 ＝
#: `"{例外型別}: {訊息}"`）。**只有例外才有**（2026-09-27 Q5-r2）—— yfinance **沒拋、只回空**
#: 時照舊回無旗標的空 Series：那與「真的沒配息」在這一層分不出來，不猜（§1）。
DIVIDENDS_FETCH_FAILED_ATTR = "fetch_failed"


@st.cache_data(ttl=TTL_1HOUR, max_entries=200, show_spinner=False)
def _cached_dividends_cached(ticker: str) -> pd.Series:
    """`cached_dividends()` 的快取層。**拋例外一律往上拋**（Q5-r2-r3 2026-09-27,
    §1.A-3(a)「只快取成功結果」;st.cache_data 不快取例外）。成功與「只回空」路徑與 TTL 同修前。"""
    import yfinance as yf
    with _proxy_env():
        _s = yf.Ticker(ticker).dividends
    if _s is None or _s.empty:
        return pd.Series(dtype=float)
    return _s


#: Q5-r2-r3:配息失敗退避（§1.A-3(b)）—— 冷卻期內同一檔不重打 Yahoo,回同一則失敗旗標。
_dividends_fail_cooldown = _FailCooldown()


def cached_dividends(ticker: str) -> pd.Series:
    """yfinance Ticker.dividends with NAS proxy + 1h cache（**只快取成功**）。

    Returns:
        pd.Series；抓不到回空 Series（不爆例外）。拋例外那一種，空 Series 的 `attrs`
        帶 `DIVIDENDS_FETCH_FAILED_ATTR`（值與內容其餘不變；不讀 attrs 的 caller 無感）。
        Q5-r2-r3:失敗**不入快取**;失敗後 `shared.fail_cooldown.FAIL_COOLDOWN_SEC` 秒內
        同一檔不重抓,回同一則失敗旗標;成功一次即解除。`.clear()` 同清快取與退避紀錄。
    """
    _hit, _gen = _dividends_fail_cooldown.begin(ticker)
    if _hit is not _FC_NO_HIT:
        return _hit
    try:
        _s = _cached_dividends_cached(ticker)
    except Exception as _e:
        print(f"[yf_proxy.dividends] {ticker}: {type(_e).__name__}: {_e}")
        _empty = pd.Series(dtype=float)
        _empty.attrs[DIVIDENDS_FETCH_FAILED_ATTR] = f"{type(_e).__name__}: {_e}"
        return _dividends_fail_cooldown.fail(ticker, _gen, _empty)
    _dividends_fail_cooldown.success(ticker)
    return _s


def _clear_cached_dividends() -> None:
    getattr(_cached_dividends_cached, "clear", lambda: None)()
    _dividends_fail_cooldown.clear()


cached_dividends.clear = _clear_cached_dividends
