"""src/data/macro/macro_cache_reader.py — Parquet 本地快取讀取 L1(C4 v18.402).

從 L2 modules 抽出的 Parquet 檔案 I/O,落實 §8.2「L2 純函式無 I/O」契約:
- 原 `src/compute/macro/macro_signal_lookback_tw.py:109 _load_parquet_safe`
- 原 `src/compute/macro/macro_validation_tw.py:40 load_twii_close_from_parquet`

§8.2 layer:L1 Data — 本地 cache 反序列化(filesystem read,非網路 I/O)。
無 Streamlit 依賴(L2 caller 為純函式契約,L1 helper 也保持無 streamlit)。

對外 API:
- `DEFAULT_PARQUET_CACHE_DIR`:預設 cache 目錄(Path("data_cache"))
- `load_parquet_safe(path, required_cols) -> DataFrame | None`:通用 safe loader
- `load_twii_close(cache_dir) -> Series`:讀 twii_ohlcv.parquet → close series
- `load_v2_chart_series(cache_dir) -> dict[str, Series]`:總經 v2 走勢卡的長歷史序列
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

DEFAULT_PARQUET_CACHE_DIR = Path("data_cache")


def load_parquet_safe(path: Path, required_cols: set) -> Optional[pd.DataFrame]:
    """安全讀 Parquet — 缺檔 / 壞檔 / 缺欄 → 回 None。

    Args:
        path: parquet 檔絕對 / 相對路徑
        required_cols: 必須存在的欄位 set;任一缺失即視為損壞,回 None

    Returns:
        DataFrame(命中)或 None(任一失敗條件)
    """
    if not path.exists():
        return None
    try:
        df = pd.read_parquet(path)
        if df.empty or not required_cols.issubset(df.columns):
            return None
        return df
    except Exception as e:  # noqa: BLE001
        print(f"[macro_cache_reader/load_parquet_safe] {path.name} 讀檔失敗:{e}")
        return None


def load_twii_close(
    cache_dir: Path = DEFAULT_PARQUET_CACHE_DIR,
) -> pd.Series:
    """讀 twii_ohlcv.parquet → close pd.Series indexed by date(Timestamp)。

    Args:
        cache_dir: parquet cache 目錄(預設 data_cache/)

    Returns:
        close pd.Series(name='twii_close',date 升序,NaN dropped);
        若檔不存在 / 壞 / 缺欄,回空 Series(name 保留)
    """
    path = cache_dir / "twii_ohlcv.parquet"
    df = load_parquet_safe(path, {"date", "close"})
    if df is None:
        return pd.Series(dtype=float, name="twii_close")
    try:
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])
        s = (df.set_index("date")["close"]
               .astype(float)
               .sort_index())
        s.name = "twii_close"
        return s.dropna()
    except Exception as e:  # noqa: BLE001
        print(f"[macro_cache_reader/load_twii_close] 處理失敗:{e}")
        return pd.Series(dtype=float, name="twii_close")


# ══════════════════════════════════════════════════════════════════════
# 極端風險閘門的兩腿取數（v19.x,2026-08-23）
# ══════════════════════════════════════════════════════════════════════
#
# 消費端:scripts/push_holdings_daily.py → src/compute/notify/market_alert_banner
# 門檻 SSOT:shared/signal_thresholds.py「極端風險閘門」段
#
# 為什麼取數在這裡而不在 L2:這兩腿要讀 parquet,是 I/O。§8.2 明文「L2 不得 I/O」,
# 而 repo 內已有一個同型待修違憲(V-RADAR-1:risk_radar 在 L2 直接打 HTTP),不再複製。

def _leg_series(df, date_col: str, val_col: str, max_age_days: int, today):
    """共用:parquet → (排序後的 DataFrame, 資料最新日期) ;過舊或空回 (None, latest)。

    回傳 latest 即使判定過舊 —— 呼叫端要能在訊息裡講出「舊到什麼時候」。
    """
    import datetime as _dt

    if df is None:
        return None, None
    d = df.copy()
    d[date_col] = pd.to_datetime(d[date_col], errors="coerce")
    d = d.dropna(subset=[date_col, val_col]).sort_values(date_col)
    if d.empty:
        return None, None
    latest = d[date_col].max()
    _today = pd.Timestamp(today or _dt.date.today())
    age = (_today.normalize() - latest.normalize()).days
    if age > max_age_days:
        print(f"[macro_cache_reader/_leg_series] {val_col} 落後 {age} 天"
              f"(最新 {latest.date()},上限 {max_age_days}）→ 判為無法評估")
        return None, latest
    return d, latest


def load_extreme_risk_legs(
    cache_dir: Path = DEFAULT_PARQUET_CACHE_DIR,
    *,
    today=None,
) -> dict:
    """極端風險閘門的兩腿 → dict。任一腿算不出來就是 None,**不補值、不猜**。

    Returns:
        {
          "twii_20d_pct":  float | None,   # 加權指數 20 交易日報酬(%)
          "foreign_5d_yi": float | None,   # 外資 5 日累計淨買賣(億 TWD)
          "twii_date":     date  | None,   # 各腿的資料最新日期(供訊息揭露)
          "foreign_date":  date  | None,
        }

    ⚠️ `twii_ohlcv.parquet` 的 **volume 欄自 2026-07-09 起每日皆為 0**
    (Yahoo Chart API 對 ^TWII 停止回傳量,見 services/market_strategy.py 註解)。
    本函式**只讀 close**,不碰 volume。

    「20 交易日」直接取 parquet 的第 20 列之前 —— parquet 的每一列就是一個交易日,
    不需要 trading calendar(這也是為什麼跌幅腿讀 parquet 而不是現抓)。
    """
    from shared.signal_thresholds import EXTREME_STALE_MAX_CALENDAR_DAYS as _MAX_AGE

    out: dict = {"twii_20d_pct": None, "foreign_5d_yi": None,
                 "twii_date": None, "foreign_date": None}

    _tw, _tw_latest = _leg_series(
        load_parquet_safe(cache_dir / "twii_ohlcv.parquet", {"date", "close"}),
        "date", "close", _MAX_AGE, today)
    out["twii_date"] = None if _tw_latest is None else _tw_latest.date()
    if _tw is not None and len(_tw) > 20:
        _c = _tw["close"].astype(float).to_numpy()
        _base = _c[-21]
        if _base > 0:
            out["twii_20d_pct"] = float((_c[-1] / _base - 1.0) * 100.0)
        else:
            print("[macro_cache_reader/load_extreme_risk_legs] 20 日前收盤 <= 0,無法算報酬")
    elif _tw is not None:
        print(f"[macro_cache_reader/load_extreme_risk_legs] TWII 僅 {len(_tw)} 列,"
              f"不足 21 列算 20 日報酬")

    _fi, _fi_latest = _leg_series(
        load_parquet_safe(cache_dir / "finmind_inst.parquet", {"date", "foreign_buy"}),
        "date", "foreign_buy", _MAX_AGE, today)
    out["foreign_date"] = None if _fi_latest is None else _fi_latest.date()
    if _fi is not None and len(_fi) >= 5:
        out["foreign_5d_yi"] = float(_fi["foreign_buy"].astype(float).to_numpy()[-5:].sum())
    elif _fi is not None:
        print(f"[macro_cache_reader/load_extreme_risk_legs] 外資僅 {len(_fi)} 列,不足 5 列")

    return out


def drop_in_progress_bar(s, now_utc):
    """丟掉「今天且美股尚未收盤」的那根**進行中** K 棒（純函式,可單測）。

    Yahoo 的 `interval=1d` 在盤中(含盤前)就會為當天開一根未收盤的棒。若直接拿
    `iloc[-1]` 當「最新收盤」、`iloc[-2]` 當「前一日收盤」,算出來的是
    **「今天到目前為止的變動」**(常常 ≈ 0%),而不是我們要的
    **「上一個完整交易日的隔夜變動」** —— 後者才是對台股開盤有領先意義的量。

    判定用 `US_SESSION_CLOSE_UTC_HOUR`(21,保守取冬令收盤)。排程時點 22:30 UTC
    在收盤之後 → 不丟棄,行為不變;手動在盤前/盤中觸發才會生效。

    ⚠️ 這只處理「進行中的棒」。若成因是「上游給過期序列」,本函式不會有作用 ——
    那一種由 caller 的 `LEAD_QUOTE_MAX_AGE_DAYS` 檢查擋下,兩者互補。

    ═══ 撤回:本函式當初的「事故」佐證是錯的(2026-08-24 當日更正)═══════════
    本 docstring 原本寫:「2026-08-24 08:42 UTC 的推播就是這個時段:提示層整行沒印,
    而同日 mynews 歸檔的同一批標的是 ^SOX -5.45% / ^IXIC -2.05%。」

    **那組數字是錯的,而且那天根本沒有事故。** -5.45% / -2.05% 取自 mynews
    `index_fetcher` 一個有 bug 的欄位(它把約五個交易日的累計變動當成隔夜變動;
    詳見該 repo 的 GOTCHAS 與 PR #147)。當天六個標的的**真實單日變動**是:

        ^GSPC +0.43%   ^IXIC +0.43%   ^DJI +0.98%
        ^SOX  -0.51%   ES=F  +0.38%   NQ=F  +0.30%

    ——**沒有一個到 -1.5% 門檻,其中四個是漲的**。所以當天提示層整行不印,
    是 `format_global_lead_line` 的正確行為,不是漏報。

    這組真實數字有兩個獨立來源交叉驗證:(1) 本 repo 自己的 production log
    `[lead_mkt]`(run 32720204915);(2) mynews 歸檔的 `last` 欄重建 —— 而該欄
    對得上獨立新聞(同期報導「道瓊大跌 703 點」,重建為 -703.84 點)。

    **保留本函式的理由**:規則本身站得住 —— 拿一根還沒收盤的 K 棒當「收盤價」
    在任何時候都是錯的,與 08-24 那天有沒有出事無關。但**當初推動它的「事故」是誤診**,
    而誤診的來源正是「用了一個沒有記錄日期的數字」。這一點比規則本身更值得記住。
    """
    from shared.global_lead_markets import US_SESSION_CLOSE_UTC_HOUR

    if s is None or len(s) < 1:
        return s
    _last_date = s.index[-1].date()
    if _last_date == now_utc.date() and now_utc.hour < US_SESSION_CLOSE_UTC_HOUR:
        return s.iloc[:-1]
    return s


def fetch_lead_market_changes(*, range_: str = "5d", now_utc=None) -> dict:
    """國際盤領先市場的**日變動 %** → {symbol: pct | None}。

    提示層用(門檻 shared/global_lead_markets.GLOBAL_LEAD_DROP_PCT)。抓不到的
    標的給 None,由 L2 `format_global_lead_line` 決定怎麼揭露 —— **本函式不吞掉
    失敗、也不用 0 代替**:0% 會被讀成「持平」,而持平和不知道是兩件事。

    取數重用既有的 `macro_core.fetch_yf_close`(走 NAS proxy 直打 Chart API),
    不另開一條 HTTP。lazy import 避免本模組被純 parquet 場景 import 時
    連帶拉起整個 macro_core 依賴鏈。

    §8.2:本函式在 L1,做網路 I/O 是對的位置。
    """
    import datetime as _dt

    from shared.global_lead_markets import LEAD_MARKETS, LEAD_QUOTE_MAX_AGE_DAYS

    _now = now_utc or _dt.datetime.now(_dt.timezone.utc)
    out: dict = {}
    for m in LEAD_MARKETS:
        try:
            from src.data.macro.macro_core import fetch_yf_close
            s = drop_in_progress_bar(fetch_yf_close(m.symbol, range_=range_), _now)
            if s is None or len(s) < 2:
                out[m.symbol] = None
                print(f"[lead_mkt] {m.symbol} 資料不足(去掉進行中棒後僅 "
                      f"{0 if s is None else len(s)} 根)")
                continue
            _prev_ts, _last_ts = s.index[-2], s.index[-1]
            _age = (_now.date() - _last_ts.date()).days
            if _age > LEAD_QUOTE_MAX_AGE_DAYS:
                out[m.symbol] = None
                print(f"[lead_mkt] {m.symbol} 報價過舊:最新 {_last_ts.date()} "
                      f"落後 {_age} 天(上限 {LEAD_QUOTE_MAX_AGE_DAYS})→ 判為未取得")
                continue
            prev, last = float(s.iloc[-2]), float(s.iloc[-1])
            if prev <= 0:
                out[m.symbol] = None
                print(f"[lead_mkt] {m.symbol} 前值 {prev} <= 0,無法算變動")
                continue
            _chg = float((last / prev - 1.0) * 100.0)
            out[m.symbol] = _chg
            # ⚠️ 這行 log 是 2026-08-24 **誤診**的直接產物(當初以為是事故,查證後
            # 那天並無漏報,見 drop_in_progress_bar 的撤回段):當時只印了極端風險兩腿,
            # 六個國際標的算出什麼**一個字都沒有**,以致於事後只能靠推論。
            # 「用了哪兩天、值多少、算出幾 %」缺一不可 —— 少了日期就分不出
            # 「進行中的棒」與「過期序列」這兩種完全不同的故障。
            print(f"[lead_mkt] {m.symbol:9s} {_prev_ts.date()} {prev:>10.2f} → "
                  f"{_last_ts.date()} {last:>10.2f} = {_chg:+.2f}%")
        except Exception as e:  # noqa: BLE001
            out[m.symbol] = None
            print(f"[lead_mkt] {m.symbol} 失敗:{type(e).__name__}: {e}")
    return out


# ══════════════════════════════════════════════════════════════════════
# 總經 v2 走勢卡的長歷史序列（2026-08-25）
# ══════════════════════════════════════════════════════════════════════
#
# 消費端:src/ui/tabs/tab_macro_v2.py（L5，經 L3 無業務加工，屬 EX-PASSTHRU-1 精神）
#
# 為什麼取數在這裡而不在 L2/L5:要讀 parquet，是 I/O。§8.2 明文「L2 不得 I/O」，
# 且 L5 直接讀檔會把 cache 路徑散到 UI。同檔上方「極端風險閘門兩腿」是同一理由。
#
# ⚠️ 為什麼只有這兩個指標:2026-08-25 盤點 16 盞燈的歷史資料，**只有這兩個**
#    有落地的長序列可畫（twii_ohlcv 4,919 列 / finmind_margin 4,943 列）。
#    其餘 14 個要嘛完全查無序列（vix / 台灣 PMI / jingqi / news_systemic），
#    要嘛只有記憶體內 14~60 日短窗（us10y / dxy / adl / fut_net，隨 session 消失）。
#    §1:沒有序列的指標**不畫圖**，由消費端改用純數值卡，不以合成資料充當走勢。

def load_v2_chart_series(
    cache_dir: Path = DEFAULT_PARQUET_CACHE_DIR,
) -> dict[str, pd.Series]:
    """讀總經 v2 走勢卡要用的長歷史序列。

    Returns:
        dict，key 為 `DangerSpec.key`，value 為 date-indexed pd.Series：
          - `"bias_240"`:台股距年線乖離 %（由 twii close 算 MA240 → 乖離）
          - `"margin"`  :融資餘額（**億元**，已由元換算）
        取不到的 key **不會出現在 dict 裡**（§1:不放空 Series 讓消費端誤以為有資料）。

    單位（§4.1）:
        bias_240 → %（與 DangerSpec.unit 一致）
        margin   → 億元（parquet 原欄 `margin_balance` 單位是**元**，
                   除以 `shared.margin_schema.TWD_PER_YI`；門檻 2500/3400 也是億）
    """
    from shared.margin_schema import TWD_PER_YI
    from shared.relative_thresholds import DEFAULT_BIAS_MA_LEN

    out: dict[str, pd.Series] = {}

    # ── bias_240:close → MA240 → 乖離 % ──────────────────────────────
    _close = load_twii_close(cache_dir)
    if len(_close) >= DEFAULT_BIAS_MA_LEN:
        try:
            _ma = _close.rolling(DEFAULT_BIAS_MA_LEN).mean()
            _bias = ((_close / _ma - 1.0) * 100.0).dropna()
            if len(_bias):
                _bias.name = "bias_240"
                out["bias_240"] = _bias
        except Exception as e:  # noqa: BLE001 — 單一序列失敗不該讓整頁炸
            print(f"[macro_cache_reader/load_v2_chart_series] bias_240 計算失敗:{e}")
    elif len(_close):
        # §1:出聲不吞。資料不足畫不出年線乖離，明講而不是偷偷用較短的均線。
        print(f"[macro_cache_reader/load_v2_chart_series] twii close 只有 "
              f"{len(_close)} 筆 < MA{DEFAULT_BIAS_MA_LEN}，不畫 bias_240"
              f"（不以較短均線冒充年線）")

    # ── margin:元 → 億 ────────────────────────────────────────────────
    _df = load_parquet_safe(cache_dir / "finmind_margin.parquet",
                            {"date", "margin_balance"})
    if _df is not None:
        try:
            _d = _df.copy()
            _d["date"] = pd.to_datetime(_d["date"])
            _s = (_d.set_index("date")["margin_balance"].astype(float)
                    .sort_index().dropna() / TWD_PER_YI)
            if len(_s):
                _s.name = "margin"
                out["margin"] = _s
        except Exception as e:  # noqa: BLE001
            print(f"[macro_cache_reader/load_v2_chart_series] margin 處理失敗:{e}")

    return out
