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
        upstream_state: 最近一次抓取的三態（B2／DEC-148；`""`／`NO_NEW_DATA`／`FETCH_FAILED`／`UNDETERMINED`），
            由 L0 `shared.upstream_state.classify_upstream` 統一判定。與 `is_stale`（資料新鮮度）、`upstream_error`
            （原樣 last_error）**各自獨立**；`""` ＝ 沒有上游問題。attrs 缺此欄但有 `upstream_error`（舊快取讀取路徑）→
            由 `upstream_error` 單獨判定（純標記字串 → UNDETERMINED，不預設成功）。
        error: `ok=False` 時的原因；`ok=True` 則 ""。
        failed: True ＝ 讀取時丟了**例外**（系統真出錯，L5 可標紅）；False 的 `ok=False` ＝ 檔不存在／壞檔／缺欄／空
            （「讀不到」，L5 標灰）。v3 §02 灰紅分離。
        source: 資料來源說明。
        ohlc_requested: 呼叫端是否要求日 K（`with_ohlc=True`）。
        ohlc_ok: 日 K 視窗是否通過 L0 `shared.twii_ohlc_contract.validate_ohlc_window`；
            None ＝ 沒要求（⛔ 不等於合格）。
        ohlc_error: 不合格的原因碼（`shared.twii_ohlc_contract` 常數）；合格或沒要求 → ""。
        ohlc_detail: 不合格的說明（含出事日期）；合格或沒要求 → ""。
        open／high／low: 日 K 開高低（**只在 `ohlc_ok is True` 才填**，與 `xs`／`close` 同一批列等長）；
            不合格 → 一律空 tuple（⛔ 不部分填、不剔除壞棒後照畫）。
        n_ohlc: 合格日 K 的根數；可少於要求的 n（資料不足 ⇒ 由 L5 顯示「不足」，⛔ 不補）。不合格 → 0。
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
    upstream_state: str = ""
    error: str = ""
    failed: bool = False
    source: str = TWII_SOURCE_TEXT
    # ── Issue #1099 PR-1：日 K OHLC（加性欄位，全部有預設值且附在最後 ⇒ 既有建構方式不受影響）──
    ohlc_requested: bool = False
    ohlc_ok: bool | None = None
    ohlc_error: str = ""
    ohlc_detail: str = ""
    open: tuple[float, ...] = ()
    high: tuple[float, ...] = ()
    low: tuple[float, ...] = ()
    n_ohlc: int = 0

    def __post_init__(self) -> None:
        # Issue #1140 C2：負的 age_days ＝ 資料日晚於基準日（未來日；L1 `compute_cache_staleness` D2 照實保留負值供診斷）。
        # 這種資料**無法判定新鮮度**：⛔ 不顯示「過期 -N 天」、⛔ 不截成 0 天、⛔ 不當 fresh／未判定的 OK。
        # 此處是三條消費路徑（收盤卡／日 K／圖 A）共用的唯一出口：天數改 None（"天數未知"）、is_stale 強制 True
        # （與 L1 D2「視為過期」同向）；原因說明 `stale_reason` 原樣保留（來源可追溯）。
        if self.age_days is not None and self.age_days < 0:
            object.__setattr__(self, "age_days", None)
            object.__setattr__(self, "is_stale", True)
        # B2(DEC-148):有 upstream_error 但沒帶 upstream_state(舊讀取路徑／直接建構)→ 由 last_error 單獨判定
        # (純空抓取標記 → UNDETERMINED,不預設成功;其他錯誤字串 → FETCH_FAILED)。判定規則只在 L0 一處。
        if not self.upstream_state and self.upstream_error:
            from shared.upstream_state import classify_upstream, upstream_state_value
            object.__setattr__(self, "upstream_state",
                               upstream_state_value(classify_upstream(self.upstream_error)[0]))


def _iso(v) -> str | None:
    """日期／Timestamp／字串 → 'YYYY-MM-DD'；None／空 → None（⛔ 不用今天代替）。"""
    if v is None:
        return None
    _s = str(v).strip()
    return _s[:10] if _s else None


def get_twii_trend_view(n_trading_days: int, *, with_ohlc: bool = False, today=None) -> TwiiTrendView:
    """加權指數最近 `n_trading_days` 個交易日的收盤＋新鮮度（`with_ohlc=True` 另附日 K OHLC 契約結果）。

    Args:
        n_trading_days: 取尾端幾列（parquet 每一列就是一個交易日）；< 1 → `ValueError`（⛔ 不默默回空）。
        with_ohlc: False（預設）＝ 原行為（只讀 `load_twii_close`）；True ＝ 改讀 `load_twii_ohlc` **一次**
            （單一快照），收盤卡欄位語意不變，另以 L0 契約驗證尾端 n 列日 K（Issue #1099 PR-1，DEC-156）。
        today: 基準日（測試注入）；None → 新鮮度沿用 L1 預設（今天），日 K 未來日判定用台北今日。
    """
    if n_trading_days < 1:
        raise ValueError(f"n_trading_days 必須 ≥ 1，收到 {n_trading_days!r}")
    if with_ohlc:
        return _get_twii_trend_view_with_ohlc(n_trading_days, today=today)
    try:
        from src.data.macro.macro_cache_reader import load_twii_close
        _s = load_twii_close() if today is None else load_twii_close(today=today)
    except Exception as _e:  # noqa: BLE001 — 讀不到就講出來（§1），由 L5 決定灰／紅
        print(f"[market_twii_view_service] load_twii_close 失敗：{_e!r}")
        return TwiiTrendView(ok=False, failed=True, error=f"{type(_e).__name__}: {_e}")
    if _s is None or len(_s) == 0:
        return TwiiTrendView(ok=False, error=_UNREADABLE_TEXT)
    _attrs = getattr(_s, "attrs", {}) or {}
    _bad = _card_price_problem(_s, _attrs, n_trading_days)
    if _bad:
        # Issue #1140 C1：收盤價必須是有限正值（與日 K 契約 `price_problem` 同一規則）；⛔ 不補 0／不剔除壞值後照畫。
        # 畫面沿用既有「讀不到」灰態字樣（不新增使用者可見文案）；具體原因只進 log。
        print(f"[market_twii_view_service] 收盤價未通過價格有效性檢查，整段不用：{_bad}")
        return TwiiTrendView(ok=False, error=_UNREADABLE_TEXT)
    return TwiiTrendView(**_close_view_kwargs(_s, _attrs, n_trading_days))


#: 讀不到（檔不存在／壞檔／缺欄／空）時的說明（灰，非例外）。
_UNREADABLE_TEXT: str = "加權指數歷史快取讀不到（檔案不存在、壞檔、缺欄或內容為空）"


def _card_price_problem(_s, _attrs: dict, n_trading_days: int) -> str:
    """收盤卡／圖 A 的價格有效性（first violation wins；合格 → `""`）。只驗**價格欄**，規則＝L0 `price_problem`。

    - 視窗內任何一筆收盤不是有限正值（≤ 0、±inf、非數值）→ 整段不合格（同日 K ⛔ 剔除壞棒後照畫）。
    - L1 `load_twii_close` 對 NaN 只 dropna（有 log）：若**最新一列**的 close 是 NaN，被剔除後尾端會是前一天的值，
      但 `attrs["as_of"]`（來自原始檔最大日期）仍是最新日 ⇒ 卡片會把舊收盤標成新資料日。兩者對不上 → 不合格。
    """
    from shared.twii_ohlc_contract import price_problem

    _tail = _s.tail(n_trading_days)
    for _idx, _v in zip(_tail.index, _tail.values):
        _code = price_problem(_v)
        if _code:
            return f"{_code} {_iso(_idx)} close={_v!r}"
    _as_of = _iso(_attrs.get("as_of"))
    if _as_of is not None and _tail.shape[0] and _as_of != _iso(_tail.index[-1]):
        return f"NOT_FINITE 最新資料日 {_as_of} 的收盤為空值（最後一筆有效收盤是 {_iso(_tail.index[-1])}）"
    return ""


def _close_view_kwargs(_s, _attrs: dict, n_trading_days: int) -> dict:
    """收盤序列＋attrs → `TwiiTrendView` 的收盤卡欄位（with_ohlc 兩條路徑共用，語意只寫一處）。"""
    _tail = _s.tail(n_trading_days)
    _is_stale = _attrs.get("is_stale")
    _age = _attrs.get("age_days")
    _up_err = str(_attrs.get("upstream_error") or "")
    _up_state = str(_attrs.get("upstream_state") or "")       # 缺 → TwiiTrendView.__post_init__ 由 upstream_error 判定
    return dict(
        ok=True,
        xs=tuple(_iso(_i) or "" for _i in _tail.index),
        close=tuple(float(_v) for _v in _tail.values),
        n_available=int(len(_s)),
        as_of=_iso(_attrs.get("as_of")) or _iso(_tail.index[-1]),
        is_stale=(bool(_is_stale) if _is_stale is not None else None),
        stale_reason=str(_attrs.get("stale_reason") or ""),
        age_days=(int(_age) if isinstance(_age, (int, float)) and not isinstance(_age, bool) else None),
        upstream_error=_up_err,
        upstream_state=_up_state,
    )


def _taipei_today():
    """台北今日（日 K 未來日判定的預設基準；台灣無 DST）。"""
    from datetime import datetime

    from shared.twii_ohlc_contract import taipei_tz
    return datetime.now(taipei_tz()).date()


def _get_twii_trend_view_with_ohlc(n_trading_days: int, *, today=None) -> TwiiTrendView:
    """`with_ohlc=True`：一次讀 `load_twii_ohlc`（單一快照）→ 收盤卡欄位＋日 K 契約結果。

    - 收盤卡欄位（ok／xs／close／as_of／is_stale…）與 `with_ohlc=False` **同語意**：close 欄 dropna 後取尾端 n 列。
    - 日 K：取**原始**（未 dropna、未去重）尾端 n 列交 L0 `validate_ohlc_window`，as_of 用卡片同一個值 ⇒
      卡片與圖同源；不合格 → `ohlc_ok=False`＋原因碼，OHLC tuple 一律空（收盤卡照常可用）。
    - 讀取丟例外 → 沿用既有 `failed=True` 路徑（紅）。
    """
    from shared.twii_ohlc_contract import (
        EMPTY, OHLC_OK, READ_FAILED, WINDOW_MISMATCH, validate_ohlc_window,
    )
    try:
        from src.data.macro.macro_cache_reader import load_twii_ohlc
        _df = load_twii_ohlc() if today is None else load_twii_ohlc(today=today)
        if _df is None or len(_df) == 0:
            return TwiiTrendView(ok=False, error=_UNREADABLE_TEXT, ohlc_requested=True, ohlc_ok=False,
                                 ohlc_error=EMPTY, ohlc_detail=_UNREADABLE_TEXT)
        _attrs = dict(getattr(_df, "attrs", {}) or {})
        _close_raw = _df["close"]
        _s = _close_raw.dropna()
        from shared.na_drop_log import log_na_drop
        log_na_drop(_close_raw, _s, tag="market_twii_view_service/with_ohlc", series="twii_ohlcv.parquet:close")
        if len(_s) == 0:
            return TwiiTrendView(ok=False, error=_UNREADABLE_TEXT, ohlc_requested=True, ohlc_ok=False,
                                 ohlc_error=EMPTY, ohlc_detail="收盤欄全為空值")
        _kw = _close_view_kwargs(_s, _attrs, n_trading_days)

        _win = _df.tail(n_trading_days)
        _dates = tuple(_iso(_i) or "" for _i in _win.index)
        _ok, _code, _detail = validate_ohlc_window(
            _dates,
            tuple(_win["open"].tolist()), tuple(_win["high"].tolist()),
            tuple(_win["low"].tolist()), tuple(_win["close"].tolist()),
            tuple((_v if isinstance(_v, str) else None) for _v in _win["fetched_at"].tolist()),
            as_of=_kw["as_of"],
            today=(today if today is not None else _taipei_today()),
        )
        if _ok and _dates != _kw["xs"]:
            # 同快照自檢：通過驗證的視窗（無 NaN close）理應與收盤卡的 dropna 尾端是同一批列；不是就 fail-closed。
            _ok, _code, _detail = False, WINDOW_MISMATCH, (
                f"日 K 視窗 {len(_dates)} 列（{_dates[:1]}…{_dates[-1:]}）≠ 收盤序列 {len(_kw['xs'])} 列")
        if not _ok:
            print(f"[market_twii_view_service] 日 K 契約不合格：{_code} {_detail}")
            return TwiiTrendView(**_kw, ohlc_requested=True, ohlc_ok=False, ohlc_error=_code, ohlc_detail=_detail)
        return TwiiTrendView(
            **{**_kw, "xs": _dates, "close": tuple(float(_v) for _v in _win["close"].tolist())},
            ohlc_requested=True, ohlc_ok=True, ohlc_error=OHLC_OK, ohlc_detail="",
            open=tuple(float(_v) for _v in _win["open"].tolist()),
            high=tuple(float(_v) for _v in _win["high"].tolist()),
            low=tuple(float(_v) for _v in _win["low"].tolist()),
            n_ohlc=len(_dates),
        )
    except Exception as _e:  # noqa: BLE001 — 讀不到就講出來（§1），由 L5 決定灰／紅
        print(f"[market_twii_view_service] load_twii_ohlc／日 K 契約失敗：{_e!r}")
        return TwiiTrendView(ok=False, failed=True, error=f"{type(_e).__name__}: {_e}",
                             ohlc_requested=True, ohlc_ok=False, ohlc_error=READ_FAILED,
                             ohlc_detail=f"{type(_e).__name__}: {_e}")
