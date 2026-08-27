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
- `read_cache_metadata(cache_dir) -> dict`:讀 `data_cache/metadata.json`(cron 的自陳狀態)
- `compute_cache_staleness(dataset, ...) -> dict`:單一 parquet 的年齡判定(§1 誠實預設)

═══ 2026-08-27 補:讀取端的過期判定(原本完全沒有)═══════════════════════════
本檔的 `load_twii_close` / `load_v2_chart_series` 原本**讀了就用,不看資料多舊** ——
上游 cron 掛掉時,總經 v2 走勢卡會拿舊 parquet 照畫,畫面上一個字都看不出來。
(實例:`finmind_m1m2.parquet` 的 `last_updated` 停在 2026-06-01、`last_error`
 是「抓取結果為空」,而校準 cron 照讀不誤。)

做法**沿用全 repo 唯一做對的那一組** —— `src/data/sector_flow/reader.py::_compute_staleness`:
  - 判不出年齡(缺 metadata / 缺日期欄 / 無法解析)→ **視為過期**,不假設新鮮;
  - 門檻走既有 L0 SSOT(`shared/staleness.py`),本檔**不新增任何門檻數值**;
  - 月頻序列(m1b_m2 的 `date` 是月初)走 `monthly_release_status`,**不**用日曆天量
    —— 理由見 `shared/staleness.py` G2 區塊(拿日頻標準量月初 as_of 會天天假紅燈)。

⚠️ **已知缺口,據實登記(本輪未修)**:年齡算出來後掛在回傳 Series 的 `.attrs`
   上,但 `services/macro_v2_service.get_chart_series()` 會把 Series 轉成
   `[(iso_date, value)]` 送進 `@st.cache_data`,**`.attrs` 在那一步就掉了**;
   `tab_macro_v2.py`(L5)也還沒有顯示過期旗標的位置。
   要讓使用者在畫面上看見,必須同時改 `services/macro_v2_service.py`(L3)與
   `src/ui/tabs/tab_macro_v2.py`(L5)—— **兩者都不在本次派工的檔案邊界內**,故未動。
   現況 = L1 已誠實算出並 print 出來,但**畫面仍看不到**。這是待辦,不是已完成。
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

DEFAULT_PARQUET_CACHE_DIR = Path("data_cache")


#: `data_cache/metadata.json` —— cron `scripts/update_macro_history.py` 每次寫的自陳狀態
#: (`datasets[<name>].last_updated` / `.row_count` / `.last_error`)。
CACHE_METADATA_NAME = "metadata.json"

#: dataset → (發布頻率, `shared.staleness.MACRO_PUBLICATION_LAG_DAYS` 的 indicator key)。
#: ⚠️ 這是**頻率分類**,不是門檻 —— 門檻一律由 `shared/staleness.py` 供給(§3.3)。
#: `finmind_m1m2` 的 `date` 欄是**資料月月初**(實測 2026-06-01),故走月頻「期」判定;
#: 其餘三個是交易日序列,走日頻天數判定。
CACHE_DATASET_CADENCE: dict[str, tuple] = {
    "twii_ohlcv":     ("daily", None),
    "finmind_inst":   ("daily", None),
    "finmind_margin": ("daily", None),
    "finmind_m1m2":   ("monthly", "m1b_m2"),
}


def read_cache_metadata(cache_dir: Path = DEFAULT_PARQUET_CACHE_DIR) -> dict:
    """讀 `data_cache/metadata.json`;缺檔 / 壞檔 → `{}`(不炸,由呼叫端判過期)。"""
    import json

    _p = cache_dir / CACHE_METADATA_NAME
    if not _p.exists():
        return {}
    try:
        _d = json.loads(_p.read_text(encoding="utf-8"))
        return _d if isinstance(_d, dict) else {}
    except Exception as e:  # noqa: BLE001 — 壞掉的 metadata 當作沒有,不該炸讀檔路徑
        print(f"[macro_cache_reader/read_cache_metadata] {_p.name} 解析失敗:{e}")
        return {}


def _as_of_from_df(df) -> Optional[object]:
    """由 parquet 的 `date` 欄取最新資料日;取不到回 None。"""
    if df is None or "date" not in getattr(df, "columns", []):
        return None
    try:
        _s = pd.to_datetime(df["date"], errors="coerce").dropna()
        return None if _s.empty else _s.max().date()
    except Exception:  # noqa: BLE001
        return None


def compute_cache_staleness(
    dataset: str,
    *,
    cache_dir: Path = DEFAULT_PARQUET_CACHE_DIR,
    df=None,
    today=None,
) -> dict:
    """單一本地 parquet 的「多舊」判定。

    Args:
        dataset: `CACHE_DATASET_CADENCE` 的 key(= parquet 檔名去掉副檔名)。
        cache_dir: cache 目錄。
        df: 已讀好的 DataFrame(避免重讀);None → 由本函式自己讀。
        today: 基準日(測試注入;None → `date.today()`)。

    Returns:
        {
          "dataset":        str,
          "is_stale":       bool,        # §1:判不出來 → True(不假設新鮮)
          "reason":         str | None,  # 為什麼判過期(講得出「舊到什麼時候」)
          "as_of":          date | None, # 資料本身的最新日期(來自 parquet 的 date 欄)
          "age_days":       int | None,  # as_of 距 today 幾個日曆天(僅日頻有意義)
          "periods_behind": int | None,  # 月頻:落後幾個發布期(≥1 = 真的漏了整期)
          "upstream_error": str | None,  # metadata 自陳的 `last_error`
          "meta_last_updated": str | None,
        }

    §1 誠實預設(照抄 `src/data/sector_flow/reader.py::_compute_staleness` 的規矩):
    **判不出年齡就當過期**,而不是當新鮮。缺 metadata、缺 date 欄、日期無法解析、
    dataset 沒登記在 `CACHE_DATASET_CADENCE` —— 一律 `is_stale=True` 並說明原因。
    """
    import datetime as _dt

    from shared.staleness import monthly_release_status, stale_days_threshold

    _today = today or _dt.date.today()
    out = {"dataset": dataset, "is_stale": True, "reason": None, "as_of": None,
           "age_days": None, "periods_behind": None,
           "upstream_error": None, "meta_last_updated": None}

    _meta = read_cache_metadata(cache_dir)
    _entry = (_meta.get("datasets") or {}).get(dataset) or {}
    out["upstream_error"] = _entry.get("last_error")
    out["meta_last_updated"] = _entry.get("last_updated")

    _cad = CACHE_DATASET_CADENCE.get(dataset)
    if _cad is None:
        out["reason"] = (f"dataset `{dataset}` 未登記於 CACHE_DATASET_CADENCE,"
                         f"判不出發布頻率 → 一律視為過期(§1 不假設新鮮)")
        return out
    _cadence, _indicator = _cad

    if df is None:
        df = load_parquet_safe(cache_dir / f"{dataset}.parquet", {"date"})
    _as_of = _as_of_from_df(df)
    if _as_of is None:
        out["reason"] = (f"{dataset}.parquet 缺檔 / 缺 `date` 欄 / 日期無法解析 → "
                         f"判不出資料日期,視為過期")
        return out
    out["as_of"] = _as_of
    out["age_days"] = (_today - _as_of).days

    if _cadence == "monthly":
        _behind, _overdue = monthly_release_status(
            _as_of, indicator=_indicator, today=_today)
        out["periods_behind"] = _behind
        if _behind is None:
            out["reason"] = (f"{dataset} 月頻新鮮度判不出來"
                             f"(indicator={_indicator!r})→ 視為過期")
        elif _behind >= 1:
            out["reason"] = (f"{dataset} 最新資料月 {_as_of}({out['age_days']} 天前),"
                             f"已落後 {_behind} 個發布期")
        else:
            out["is_stale"] = False
            if _overdue:
                out["reason"] = f"{dataset} 下一期已逾原定發布日 {_overdue} 天(仍在緩衝內)"
        return out

    _thr = stale_days_threshold(_cadence)
    if out["age_days"] > _thr:
        out["reason"] = (f"{dataset} 最新資料日 {_as_of},距今 {out['age_days']} 天,"
                         f"超過 {_cadence} 門檻 {_thr} 天")
    else:
        out["is_stale"] = False
    return out


def _attach_staleness(series, dataset: str, *, cache_dir: Path, df=None, today=None):
    """把 staleness 判定掛到回傳 Series 的 `.attrs`(schema-additive,不改回傳型別)。

    過期時**一定 print 一行** —— §1「出聲不吞」。⚠️ 但 print 只進 log,
    畫面仍看不到(檔頭「已知缺口」段有記)。
    """
    try:
        _st = compute_cache_staleness(dataset, cache_dir=cache_dir, df=df, today=today)
    except Exception as e:  # noqa: BLE001 — 判定本身壞掉不該讓讀檔路徑炸
        print(f"[macro_cache_reader/_attach_staleness] {dataset} 判定失敗:{e}")
        return series
    try:
        series.attrs["cache_dataset"] = dataset
        series.attrs["is_stale"] = _st["is_stale"]
        series.attrs["stale_reason"] = _st["reason"]
        series.attrs["as_of"] = _st["as_of"]
        series.attrs["age_days"] = _st["age_days"]
        series.attrs["upstream_error"] = _st["upstream_error"]
    except Exception:  # noqa: BLE001 — 極舊 pandas 無 .attrs;不影響資料本身
        pass
    if _st["is_stale"] or _st["upstream_error"]:
        print(f"[macro_cache_reader] ⚠️ {dataset} 判為過期/上游有錯:"
              f"{_st['reason'] or '—'}"
              + (f";metadata.last_error={_st['upstream_error']!r}"
                 if _st["upstream_error"] else ""))
    return series


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
    *,
    today=None,
) -> pd.Series:
    """讀 twii_ohlcv.parquet → close pd.Series indexed by date(Timestamp)。

    回傳的 Series 帶 `.attrs`(`is_stale` / `stale_reason` / `as_of` / `age_days` /
    `upstream_error`),過期時另 print 一行。**不改回傳型別、不擋資料** ——
    判斷要不要顯示降級是消費端的事,本層只負責把事實講出來。

    Args:
        cache_dir: parquet cache 目錄(預設 data_cache/)
        today: 過期判定的基準日(測試注入;None → 今天)

    Returns:
        close pd.Series(name='twii_close',date 升序,NaN dropped);
        若檔不存在 / 壞 / 缺欄,回空 Series(name 保留)
    """
    path = cache_dir / "twii_ohlcv.parquet"
    df = load_parquet_safe(path, {"date", "close"})
    if df is None:
        return pd.Series(dtype=float, name="twii_close")
    try:
        _raw = df
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])
        s = (df.set_index("date")["close"]
               .astype(float)
               .sort_index())
        s.name = "twii_close"
        s = s.dropna()
        # 2026-08-27:回傳前掛上「這份 cache 多舊」。`.attrs` 是 schema-additive,
        # 既有 caller(取值 / 算 MA)完全不受影響;過期時另有一行 log(§1 出聲不吞)。
        return _attach_staleness(s, "twii_ohlcv", cache_dir=cache_dir,
                                 df=_raw, today=today)
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
    *,
    today=None,
) -> dict[str, pd.Series]:
    """讀總經 v2 走勢卡要用的長歷史序列。

    每條回傳的 Series 都帶 `.attrs`(`is_stale` / `stale_reason` / `as_of` /
    `age_days` / `upstream_error`),來源 parquet 過期時另 print 一行(§1 出聲不吞)。
    **dict 的 key 集合與 Series 內容一字未改** —— 這是 schema-additive 的附掛,
    既有消費端(`services/macro_v2_service.get_chart_series`)行為零變化。
    ⚠️ 但也因此**畫面目前仍看不到過期旗標**,原因與待辦見檔頭「已知缺口」段。

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
    _close = load_twii_close(cache_dir, today=today)
    if len(_close) >= DEFAULT_BIAS_MA_LEN:
        try:
            _ma = _close.rolling(DEFAULT_BIAS_MA_LEN).mean()
            _bias = ((_close / _ma - 1.0) * 100.0).dropna()
            if len(_bias):
                _bias.name = "bias_240"
                # bias_240 由 twii close 推導 → 新鮮度**就是** twii_ohlcv 的新鮮度。
                # rolling/dropna 之後 `.attrs` 不保證留著,故從 `_close` 複製一份;
                # 直接複製而不重算,避免同一次呼叫把 parquet 讀兩遍。
                try:
                    _bias.attrs.update(dict(_close.attrs))
                except Exception:  # noqa: BLE001
                    pass
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
                out["margin"] = _attach_staleness(
                    _s, "finmind_margin", cache_dir=cache_dir, df=_df, today=today)
        except Exception as e:  # noqa: BLE001
            print(f"[macro_cache_reader/load_v2_chart_series] margin 處理失敗:{e}")

    return out
