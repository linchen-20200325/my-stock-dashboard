"""scripts/update_sector_flow.py — 板塊資金泡泡圖每日資料管線(L1 cron entrypoint)。

資料流(entrypoint 編排 L1 fetch → L2 pure → parquet;類比 update_macro_history.py)
==================================================================================
  _get_t86_day / _get_tpex_day (L1, 三大法人淨買超【張】) ┐
  fetch_twse_close_day / fetch_tpex_close_day (L1, 收盤【元】)├─→ sector_flow.compute_* (L2, 純)
  fetch_industry_map_bulk (L1, 產業別)                    ┘         ↓
                                          data_cache/sector_flow/daily_net.parquet(SSOT 日頻長表)
                                          data_cache/sector_flow/bubble_latest.json(秒讀泡泡座標)
                                          data_cache/sector_flow/metadata.json

每晚 TW 17:30(收盤後)跑:
- incremental:讀既有 parquet last_date → 只補 (last+1 .. today) 的交易日(通常 1 日)
- --bootstrap:回抓近 `--days` 日曆日(預設 30 ≈ 20 交易日,湊滿 WINDOW_SIZE)
- 走與畫面同源的 L1 fetcher(T86 selectType=ALL / TPEX 官方新網站 insti/dailyTrade / MI_INDEX / TPEX 官方新網站 afterTrading/otc;批 Z41)
- 直連即可(fetch_url 內 PROXY_URL 未設自動降級直連,官方 endpoint 全球可達)

§1 Fail Loud, Never Fake
------------------------
- 某交易日**三大法人全空**(假日/來源全敗)→ 該日整日跳過,不寫假(§4.6 自然排除)。
- 某日有法人淨額但**收盤全缺** → L2 inner-join 會剔除該日全部股 + coverage 計數;
  metadata 記 `days_missing_price` 供排查(不補價、不 ffill,§4.6 停牌不可 ffill)。
- **全部交易日皆無有效資料** → 不覆寫既有 parquet + 非零 exit(§1 寧缺勿錯)。
- 冪等(§5):同交易日重跑覆蓋同 (date,sector) 列(dedupe keep='last'),不產重複。
  批 Z41:本次**實際寫入**的日子,寫入前先刪掉 parquet 中該日**所有**舊列(不只同 sector 的列),
  避免舊板塊列殘留(例:舊列含已不存在的板塊)。

批 Z41(客戶 Q-z27=A 受控遷移):R1 上櫃(TPEx)自動回補
------------------------------------------------------
- TPEx 法人 / 收盤已改接櫃買中心官方新網站 JSON(L1 守衛見各 fetcher)。
- 每次執行候選日 = 新日期 ∪ 上次 unresolved_days ∪ **parquet 最近 WINDOW_SIZE 個交易日中
  `tpex_ok` 不為 True 的日子**(含舊列無旗標 → NA);回補日單次上限 `_TPEX_BACKFILL_MAX_DAYS`。
- **每日最多一次**:metadata `tpex_backfill.attempted_on` == 今天 → 本次不再回補(TPEx 仍故障時
  不會同日反覆轟炸;請求間無額外節流,沿用各 fetcher 既有行為)。
- 回補日重抓成功 → 先刪該日舊列再寫新列(`tpex_ok=True`、source 含 TPEx);TPEx 仍失敗 →
  重寫為只含上市(`tpex_ok=False`,下次再試);回補日 TWSE 這次失敗 / 兩邊回空 → **保留既有列不動**,
  不列入 unresolved_days(該日已有上市資料)。
- 窗口內全部 `tpex_ok=True` 後,`bubble_latest.json.tpex_complete` 轉 True,UI「目前僅含上市資料」
  自動消失(Z39 既有資料驅動判斷)。metadata 記 `backfilled_days` 與 `tpex_backfill` 明細。

批 Z39(客戶 Q-z26=A / Q-z28=A):逐日分市場判定(上市 TWSE / 上櫃 TPEx 各自成敗)
------------------------------------------------------------------------------
- TWSE ok ＝ T86 非空 且 MI_INDEX 收盤非空 且 兩者代號交集 > 0。
- TPEx ok ＝ 法人非空 且 `get_tpex_day_status(ds) == "ok"` 且 TPEx 收盤非空 且 `get_tpex_close_status(ds) == "ok"`(批 Z41 補)且 交集 > 0。
- **invariant**:當日 TWSE/TPEx 任一有法人資料(交易日)而 TPEx 回空 / 非 JSON / 欄位驗證失敗 /
  收盤空 / 交集 0 → TPEx **失敗**(不是假日),不得標 TPEx success;該日 TPEx 法人列**不納入**
  彙總(讓該日一致只含上市),`source` 只列實際成功的市場。
- TWSE 失敗(僅 TPEx 成功或兩邊都失敗)的交易日 → **不寫入**,記入 metadata `unresolved_days`。
- 批 Z39 修正(QA N1):`unresolved_days` **跨次執行累積、會被重抓** —— 每次執行先讀上一份
  metadata 的 `unresolved_days`,落在近 `_UNRESOLVED_RETRY_DAYS` 日曆天內(平日)者併入本次候選日;
  重抓成功 → 寫入並自清單移除;仍失敗 → 保留;重抓時兩邊法人都回空(上次已知是交易日)→ 仍保留
  (不得因來源全掛被誤判成假日而消失);超出回溯窗者移出清單並記 `fetch_diag.unresolved_expired`。
- 兩邊法人都空 → 假日/休市(跳過)。
- 法人分項缺鍵 → NaN(不是 0);bubble_latest.json 的 NaN 一律寫成 `null`(不寫非標準 NaN token)。

批 Z43(客戶 Q-z29＝A):產業別改依官方產業代碼選列 + 同義板塊標準化合併
------------------------------------------------------------------------
- 產業別:`fetch_industry_map_bulk()`(L1)改依官方產業代碼選列;完整選列紀錄(FinMind 全部原始列、
  官方市場/代碼/名稱/端點、chosen label/rule)落地 `industry_raw.json`(原始資料不覆寫、可追溯);
  `ticker_sector.json` 維持扁平 {代號: chosen label}。某市場官方端點失敗 → 該市場官方查無的代號
  沿用上一份 `industry_raw.json` 的 chosen(有才沿用),metadata.warnings 記錄。
- 寫入列帶 `industry_scheme`(＝`shared.industry_codes.INDUSTRY_SCHEME_VERSION`;官方端點失敗日加後綴)。
  窗口內 `industry_scheme` 缺 / ≠ 現行版本的日子併入 R1 回補(沿用上限 25 日、每日一次、先刪舊列、
  industry_ok/H1 守衛照舊);寫入後即為現行版本 → 不會無限回補。
- 泡泡:`daily_net.parquet` 的 `sector` **維持原始標籤**;只在算泡泡前以 L2 `canonicalize_sector_daily`
  (別名表 SSOT `SECTOR_CANONICAL_ALIASES`)重新彙總到標準化軸(缺值不補 0、任一成員 NaN → NaN)。
  `bubble_latest.json` 每板塊新增 `members`(原始標籤)、頂層新增 `sector_aliases_version`;metadata
  `bubble_window` 另記原始軸 / 標準軸的板塊數與缺席格數。

CLI
===
    python scripts/update_sector_flow.py                 # 每晚增量(補最新交易日)
    python scripts/update_sector_flow.py --bootstrap     # 回抓近 30 日曆日
    python scripts/update_sector_flow.py --days 45       # 自訂 bootstrap 回溯日曆天
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# repo root 上 sys.path(同 update_macro_history / update_fundamentals_snapshot 慣例)
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from shared.sector_flow_thresholds import (  # noqa: E402
    INDUSTRY_MAP_MAX_SHRINK_RATIO,
    WINDOW_SIZE,
)
from shared.industry_codes import (  # noqa: E402
    INDUSTRY_SCHEME_DEGRADED_SUFFIX,
    INDUSTRY_SCHEME_VERSION,
)
from shared.sector_flow_thresholds import SECTOR_ALIASES_VERSION, canonical_sector  # noqa: E402
from src.compute.sector_flow import (  # noqa: E402
    canonicalize_sector_daily,
    compute_bubble,
    compute_sector_daily_net,
)
from src.data.core.data_loader_inst_fetchers import (  # noqa: E402
    TPEX_DAY_STATUS_OK,
    _get_t86_day,
    _get_tpex_day,
    get_tpex_day_status,
)
from src.data.stock.market_close_fetcher import (  # noqa: E402
    apply_prev_chosen,
    fetch_industry_map_bulk,
    fetch_tpex_close_day,
    fetch_twse_close_day,
    get_last_industry_raw,
    get_tpex_close_status,
    industry_map_from_raw,
)

CACHE_DIR = Path("data_cache/sector_flow")
PARQUET_PATH = CACHE_DIR / "daily_net.parquet"
BUBBLE_PATH = CACHE_DIR / "bubble_latest.json"
META_PATH = CACHE_DIR / "metadata.json"
#: Stage 2 UI 秒讀:{裸股號: 產業別},供把使用者持股對映板塊(highlight)。
TICKER_SECTOR_PATH = CACHE_DIR / "ticker_sector.json"
#: 批 Z43:產業別完整選列紀錄(原始列 + 官方 + chosen)檔名;路徑一律 `CACHE_DIR / 本名`(隨 CACHE_DIR)。
INDUSTRY_RAW_NAME = "industry_raw.json"

#: bootstrap 預設回溯日曆天(≈ 20 交易日 + 週末/短假緩衝,湊滿 WINDOW_SIZE)。
_DEFAULT_BOOTSTRAP_DAYS = 30
#: 批 Z39 修正(QA N1):上一份 metadata 的 unresolved_days 只重抓近 N 日曆天內者
#: (= bootstrap 回溯窗,涵蓋泡泡圖 WINDOW_SIZE 交易日;更舊的已不在窗口內)。
_UNRESOLVED_RETRY_DAYS = _DEFAULT_BOOTSTRAP_DAYS
#: 交易日軸鍵。
_DEDUPE_KEYS = ["date", "sector"]
#: 批 Z39:`source` 欄依日只列實際成功使用的市場。
_SOURCE_TWSE = "TWSE:T86+MI_INDEX"
#: 批 Z41:TPEx 改接官方新網站(法人 insti/dailyTrade + 收盤 afterTrading/otc);§2.2 provenance 同步。
_SOURCE_TPEX = "TPEX:insti/dailyTrade+afterTrading/otc"
#: 批 Z41 R1:單次執行回補「tpex_ok 不為 True」的窗口內交易日上限(> WINDOW_SIZE,只作安全上限)。
_TPEX_BACKFILL_MAX_DAYS = 25


# ── I/O helpers(照 update_macro_history 範式)────────────────────────────
def _load_existing() -> pd.DataFrame | None:
    if not PARQUET_PATH.exists():
        return None
    try:
        return pd.read_parquet(PARQUET_PATH)
    except Exception as e:
        print(f"[sector_flow] 讀既有 parquet 失敗:{type(e).__name__}: {e}")
        return None


def _last_date(df: pd.DataFrame | None) -> _dt.date | None:
    if df is None or df.empty or "date" not in df.columns:
        return None
    try:
        return pd.to_datetime(df["date"]).max().date()
    except Exception:
        return None


def _merge_dedupe(old: pd.DataFrame | None, new: pd.DataFrame) -> pd.DataFrame:
    """合併 old + new,按 (date,sector) 去重保留最新,排序。"""
    if old is None or old.empty:
        out = new
    else:
        out = pd.concat([old, new], ignore_index=True)
    out["date"] = pd.to_datetime(out["date"]).dt.normalize()
    out = (out.drop_duplicates(subset=_DEDUPE_KEYS, keep="last")
              .sort_values(_DEDUPE_KEYS).reset_index(drop=True))
    return out


def _today() -> _dt.date:
    """執行日(台灣 cron 當地日)。獨立成函式供測試注入。"""
    return _dt.date.today()


def _load_prev_unresolved() -> list[str]:
    """上一份 metadata.json 的 `unresolved_days`(YYYYMMDD 字串)。檔缺 / 壞檔 → [](印 log)。"""
    if not META_PATH.exists():
        return []
    try:
        _v = json.loads(META_PATH.read_text(encoding="utf-8")).get("unresolved_days")
    except Exception as e:  # noqa: BLE001 — 壞檔不得讓 cron 整個炸;印出來
        print(f"[sector_flow] ⚠️ 讀上一份 metadata 失敗({type(e).__name__}: {e})"
              "→ 本次無法重抓上次的 unresolved_days")
        return []
    if not isinstance(_v, list):
        return []
    return [str(x) for x in _v]


def _split_retry_unresolved(prev: list[str], today: _dt.date
                            ) -> tuple[list[_dt.date], list[str]]:
    """上一份 unresolved_days → (本次要重抓的日期, 超出回溯窗 / 無法解析而移出的日期字串)。"""
    retry: list[_dt.date] = []
    expired: list[str] = []
    _floor = today - _dt.timedelta(days=_UNRESOLVED_RETRY_DAYS)
    for ds in sorted(set(prev)):
        try:
            d = _dt.datetime.strptime(ds, "%Y%m%d").date()
        except ValueError:
            expired.append(ds)
            continue
        if _floor <= d <= today and d.weekday() < 5:
            retry.append(d)
        else:
            expired.append(ds)
    return retry, expired


def _carry_unresolved(diag: dict, retry: list[_dt.date], expired: list[str]) -> None:
    """把上次未解的日子併回本次 diag(就地):重抓成功 → 已不在清單;仍失敗 → 本次已列;
    重抓時兩邊都回空(上次已知是交易日)→ 保留,不當假日丟掉。"""
    _unres = set(diag.get("unresolved_days") or [])
    for d in retry:
        ds = d.strftime("%Y%m%d")
        if (diag.get("per_day") or {}).get(ds, {}).get("holiday"):
            _unres.add(ds)
            print(f"[sector_flow] ⚠️ {ds} 為上次未解日,本次重抓兩邊都回空 → 仍列 unresolved_days")
    diag["unresolved_days"] = sorted(_unres)
    diag["unresolved_retried"] = sorted(d.strftime("%Y%m%d") for d in retry)
    diag["unresolved_expired"] = sorted(expired)


def _is_false(v) -> bool:
    return v is False or v is np.False_


def _industry_bad_dates(df: pd.DataFrame | None) -> set:
    """批 Z41 修正二(QA R1):`industry_ok` **明確為 False** 的日子(Timestamp 集合)。

    ⚠️ 語意刻意與 `tpex_ok` 相反:舊列無 `industry_ok` 欄 / NA → 視為**可信**(不納入),
    只有產業別守衛擋下期間寫入的日子(明確 False)才算 —— 否則 Z41 之前寫入的整窗舊列會被
    無限回補。
    """
    if df is None or df.empty or "industry_ok" not in df.columns or "date" not in df.columns:
        return set()
    _d = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    _bad = df["industry_ok"].map(_is_false)
    return set(_d[_bad.to_numpy()].dropna())


def _scheme_stale_dates(df: pd.DataFrame | None) -> set:
    """批 Z43:`industry_scheme` 缺欄 / NA / ≠ `INDUSTRY_SCHEME_VERSION` 的日子(Timestamp 集合)。

    舊取法(每檔取 FinMind 第一列)寫入的日子 → 需以官方代碼選列重算;同日任一列不符即算。
    """
    if df is None or df.empty or "date" not in df.columns:
        return set()
    _d = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    if "industry_scheme" not in df.columns:
        return set(_d.dropna())
    _bad = df["industry_scheme"].map(lambda v: not (isinstance(v, str) and v == INDUSTRY_SCHEME_VERSION))
    return set(_d[_bad.to_numpy()].dropna())


def _tpex_backfill_days(existing: pd.DataFrame | None, today: _dt.date) -> list[_dt.date]:
    """批 Z41 R1:parquet 最近 WINDOW_SIZE 個交易日中**需重算**的日子:
    `tpex_ok` 不為 True(舊列無欄 → NA 也算),或(批 Z41 修正二 QA R1)`industry_ok` **明確為 False**
    (產業別異常期間寫入、全歸「未分類」;舊列無欄 / NA → 可信,不納入,見 `_industry_bad_dates`),
    或(批 Z43)`industry_scheme` 缺 / ≠ 現行版本(見 `_scheme_stale_dates`)。

    同日任一列非 True 即算(同日各板塊旗標相同;保守取「全為 True 才算成功」)。
    超過 `_TPEX_BACKFILL_MAX_DAYS` → 取最近的那些。
    """
    if existing is None or existing.empty or "date" not in existing.columns:
        return []
    _d = pd.to_datetime(existing["date"], errors="coerce").dt.normalize()
    _dates = sorted(x for x in _d.dropna().unique() if pd.Timestamp(x).date() <= today)
    recent = _dates[-int(WINDOW_SIZE):]
    _ind_bad = _industry_bad_dates(existing) | _scheme_stale_dates(existing)
    if "tpex_ok" in existing.columns:
        _ok = existing["tpex_ok"].map(lambda v: v is True or v is np.True_)
        _all_ok = _ok.groupby(_d).all()
        out = [pd.Timestamp(x).date() for x in recent
               if not bool(_all_ok.get(x, False)) or pd.Timestamp(x) in _ind_bad]
    else:
        out = [pd.Timestamp(x).date() for x in recent]
    return out[-_TPEX_BACKFILL_MAX_DAYS:]


def _load_prev_backfill_attempt() -> str | None:
    """上一份 metadata 的 `tpex_backfill.attempted_on`(ISO 日期);缺 / 壞檔 → None。"""
    if not META_PATH.exists():
        return None
    try:
        _v = (json.loads(META_PATH.read_text(encoding="utf-8")).get("tpex_backfill") or {})
    except Exception as e:  # noqa: BLE001 — 壞檔不得讓 cron 整個炸;印出來
        print(f"[sector_flow] ⚠️ 讀上一份 metadata(tpex_backfill)失敗({type(e).__name__}: {e})")
        return None
    return _v.get("attempted_on") if isinstance(_v, dict) else None


def _settle_backfill(diag: dict, bf_days: list[_dt.date], attempted_on: str | None,
                     candidates: list[_dt.date], skipped: str | None) -> None:
    """批 Z41 R1:回補結果併入 diag(就地)。回補日(已在 parquet)這次 TWSE 失敗 → 移出
    unresolved_days(既有上市列保留不動,不是「未寫入」)。"""
    _pd = diag.get("per_day") or {}
    _bf = [d.strftime("%Y%m%d") for d in bf_days]
    ok = [ds for ds in _bf if _pd.get(ds, {}).get("written") and _pd.get(ds, {}).get("tpex_ok")]
    kept = [ds for ds in _bf if not _pd.get(ds, {}).get("written")]
    diag["unresolved_days"] = [ds for ds in (diag.get("unresolved_days") or []) if ds not in set(_bf)]
    diag["tpex_backfill"] = {
        "attempted_on": attempted_on,
        "candidates": [d.strftime("%Y%m%d") for d in candidates],
        "attempted": _bf,
        "backfilled_days": ok,
        "still_twse_only": [ds for ds in _bf if ds not in ok and ds not in kept],
        "kept_existing": kept,
        "skipped": skipped,
    }
    if _bf:
        print(f"[sector_flow] TPEx 回補:嘗試 {len(_bf)} 日、成功 {len(ok)} 日 {ok};"
              f"仍只含上市 {diag['tpex_backfill']['still_twse_only']};保留既有 {kept}")


def _candidate_trading_days(today: _dt.date, existing: pd.DataFrame | None,
                            bootstrap: bool, days: int) -> list[_dt.date]:
    """要抓的候選日曆日(已濾週末)。假日由 fetcher 回空自然排除(§4.5 自證法)。"""
    if bootstrap or existing is None or existing.empty:
        start = today - _dt.timedelta(days=max(1, days))
    else:
        last = _last_date(existing)
        start = (last + _dt.timedelta(days=1)) if last else (
            today - _dt.timedelta(days=_DEFAULT_BOOTSTRAP_DAYS))
    out: list[_dt.date] = []
    d = start
    while d <= today:
        if d.weekday() < 5:            # 只保留平日(週末 TWSE/TPEX 必無資料)
            out.append(d)
        d += _dt.timedelta(days=1)
    return out


# ── 抓取:逐交易日組 inst(張)+ price(元)長表 ────────────────────────────
def _collect_days(days: list[_dt.date]) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """對每候選日抓 T86+TPEX 法人 + TWSE+TPEX 收盤 → 兩個長表 + 診斷 meta。

    批 Z39:逐日分市場判定成敗(規則見檔頭);只把**成功市場**的法人列與收盤放進長表。
    diag 追加 `per_day[ds]`(各源筆數 / TPEx 狀態 / twse_ok / tpex_ok / written)與
    `unresolved_days`(TWSE 失敗、未寫入的交易日)。回傳仍為 3-tuple。
    """
    inst_rows: list[dict] = []
    price_rows: list[dict] = []
    diag = {"days_fetched": 0, "days_holiday_or_empty": 0, "days_missing_price": 0,
            "per_day": {}, "unresolved_days": []}
    _nan = float("nan")
    for d in days:
        ds = d.strftime("%Y%m%d")
        t86 = _get_t86_day(ds) or {}
        tpex = _get_tpex_day(ds) or {}
        _day = {"twse_inst": len(t86), "twse_close": 0, "tpex_inst": len(tpex),
                "tpex_close": 0, "tpex_inst_status": get_tpex_day_status(ds),
                "tpex_close_status": None, "twse_ok": False, "tpex_ok": False,
                "holiday": False, "written": False}
        diag["per_day"][ds] = _day
        if not t86 and not tpex:
            diag["days_holiday_or_empty"] += 1
            _day["holiday"] = True
            continue   # §1/§4.6:兩邊都空 = 假日/休市 → 整日跳過,不寫假
        diag["days_fetched"] += 1
        twse_close = fetch_twse_close_day(ds) or {}
        tpex_close = fetch_tpex_close_day(ds) or {}
        _day["twse_close"] = len(twse_close)
        _day["tpex_close"] = len(tpex_close)
        _day["tpex_close_status"] = get_tpex_close_status(ds)
        if not twse_close and not tpex_close:
            # 有法人淨額但當日收盤全缺 → 該日金額無法換算(§1 不補價)
            diag["days_missing_price"] += 1
            print(f"[sector_flow] ⚠️ {ds} 有法人淨額但收盤全缺 → 該日金額不計")
        twse_ok = bool(t86) and bool(twse_close) and bool(set(t86) & set(twse_close))
        # invariant:TPEx 0 筆 / parser failure / 欄位未驗證 / 收盤空 / 交集 0 → 不得標成功
        tpex_ok = (bool(tpex) and _day["tpex_inst_status"] == TPEX_DAY_STATUS_OK
                   and bool(tpex_close) and _day["tpex_close_status"] == "ok"
                   and bool(set(tpex) & set(tpex_close)))
        _day["twse_ok"], _day["tpex_ok"] = bool(twse_ok), bool(tpex_ok)
        if not twse_ok:
            # TWSE 失敗(含只有 TPEx 成功)→ 不寫入,交 metadata 列 unresolved(不寫半套日)
            diag["unresolved_days"].append(ds)
            print(f"[sector_flow] ⚠️ {ds} 上市(TWSE)未成功(法人 {len(t86)} / 收盤 "
                  f"{len(twse_close)})→ 該日不寫入,列 unresolved_days")
            continue
        if not tpex_ok:
            print(f"[sector_flow] ⚠️ {ds} 上櫃(TPEx)未成功(法人 {len(tpex)} 狀態 "
                  f"{_day['tpex_inst_status']} / 收盤 {len(tpex_close)} 狀態 "
                  f"{_day['tpex_close_status']})→ 該日只含上市")
        _day["written"] = True
        _inst = {**tpex, **t86} if tpex_ok else dict(t86)
        for code, v in _inst.items():
            v = v if isinstance(v, dict) else {}
            inst_rows.append({
                "date": d, "stock_id": str(code).strip(),
                # 批 Z39:缺鍵 = 未取得(NaN),不是 0(Q-z26=A)
                "foreign_lots": v.get("外資", _nan),
                "trust_lots": v.get("投信", _nan),
                "dealer_lots": v.get("自營商", _nan),
            })
        close_map: dict = {}
        if tpex_ok:
            close_map.update(tpex_close)
        close_map.update(twse_close)   # 上市覆蓋上櫃(代號不重疊)
        for code, close in close_map.items():
            price_rows.append({"date": d, "stock_id": str(code).strip(),
                               "close": close})
    inst_df = pd.DataFrame(inst_rows) if inst_rows else pd.DataFrame(
        columns=["date", "stock_id", "foreign_lots", "trust_lots", "dealer_lots"])
    price_df = pd.DataFrame(price_rows) if price_rows else pd.DataFrame(
        columns=["date", "stock_id", "close"])
    return inst_df, price_df, diag


def _json_safe(o):
    """批 Z39:NaN / ±inf → None(JSON null);numpy 純量 → Python 原生;遞迴 dict / list。"""
    if isinstance(o, dict):
        return {str(k): _json_safe(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_json_safe(v) for v in o]
    if hasattr(o, "item") and not isinstance(o, (str, bytes)):
        try:
            o = o.item()
        except (ValueError, TypeError):
            pass
    if isinstance(o, float) and not math.isfinite(o):
        return None
    return o


def _day_flags_frame(diag: dict) -> pd.DataFrame:
    """per_day → DataFrame[date, twse_ok, tpex_ok, source](只含已寫入日)。"""
    rows = []
    for ds, v in (diag.get("per_day") or {}).items():
        if not v.get("written"):
            continue
        rows.append({
            "date": pd.Timestamp(_dt.datetime.strptime(ds, "%Y%m%d")).normalize(),
            "twse_ok": bool(v.get("twse_ok")), "tpex_ok": bool(v.get("tpex_ok")),
            "source": _SOURCE_TWSE + (f" / {_SOURCE_TPEX}" if v.get("tpex_ok") else ""),
        })
    out = pd.DataFrame(rows, columns=["date", "twse_ok", "tpex_ok", "source"])
    out["date"] = pd.to_datetime(out["date"]).astype("datetime64[ns]")
    return out


def _norm_flag_cols(df: pd.DataFrame) -> pd.DataFrame:
    """twse_ok / tpex_ok / industry_ok → nullable boolean;舊列(無旗標 → NaN/None)為 <NA>。

    `twse_ok`/`tpex_ok` 的 NA ＝ 未知 ≠ True;`industry_ok`(批 Z41 修正二)的 NA ＝ 舊列,
    回補時視為可信(只有明確 False 才重算,見 `_industry_bad_dates`)。
    """
    for c in ("twse_ok", "tpex_ok", "industry_ok"):
        if c in df.columns:
            df[c] = pd.array([True if (v is True or v is np.True_) else
                              (False if (v is False or v is np.False_) else pd.NA)
                              for v in df[c]], dtype="boolean")
    return df


def _markets_summary(diag: dict) -> dict:
    """本次抓取的分市場成敗(假日不計)。

    批 Z39 修正(QA N7a):TPEx 的 ok 只計**已寫入**日 —— 「TPEx 成功但 TWSE 失敗、未寫入」
    的日子 TPEx 資料並未入庫,不得算進 TPEx ok_days;該類日子列 `not_written_dates`
    (兩個市場同一份,= TWSE 未成功日),TPEx fail 只計「已寫入但不含上櫃」的日子。
    """
    out = {}
    _pd = diag.get("per_day") or {}
    _trading = {ds: v for ds, v in _pd.items() if not v.get("holiday")}
    _not_written = sorted(ds for ds, v in _trading.items() if not v.get("written"))
    for mkt, key in (("TWSE", "twse_ok"), ("TPEx", "tpex_ok")):
        if mkt == "TWSE":
            ok = sorted(ds for ds, v in _trading.items() if v.get(key))
            fail = sorted(ds for ds, v in _trading.items() if not v.get(key))
        else:
            ok = sorted(ds for ds, v in _trading.items()
                        if v.get("written") and v.get(key))
            fail = sorted(ds for ds, v in _trading.items()
                          if v.get("written") and not v.get(key))
        out[mkt] = {"ok_days": len(ok), "fail_days": len(fail),
                    "ok_dates": ok, "fail_dates": fail,
                    "not_written_dates": _not_written}
    return out


def _window_rows(full: pd.DataFrame) -> pd.DataFrame:
    """批 Z43:長表只留最近 WINDOW_SIZE 個交易日(與 `compute_bubble` 內部取窗一致)。"""
    if full is None or full.empty or "date" not in full.columns:
        return full
    _d = pd.to_datetime(full["date"], errors="coerce").dt.normalize()
    _win = sorted(_d.dropna().unique())[-int(WINDOW_SIZE):]
    return full[_d.isin(_win).to_numpy()]


def _axis_meta(m: dict) -> dict:
    return {k: m.get(k) for k in ("n_sectors", "n_trading_days_used", "n_absent_cells",
                                  "n_missing_value_cells", "n_days_tpex_ok")}


def _write_bubble_json(full: pd.DataFrame) -> dict:
    """由完整長表算最新泡泡座標,落 bubble_latest.json(Stage 2 秒讀)。

    批 Z39:NaN → `null`(`allow_nan=False` 守門,不寫非標準 NaN token);
    `tpex_complete` ＝ 窗口內每個交易日 TPEx 皆成功(舊列無旗標 → 非 True → False);
    回傳 meta 追加 `tpex_complete`。
    批 Z43:先取窗口(近 WINDOW_SIZE 交易日)→ L2 `canonicalize_sector_daily` 標準化軸 → `compute_bubble`;
    長表(原始標籤)不變。每板塊加 `members`(原始標籤),頂層加 `sector_aliases_version`;
    回傳 meta 追加 `raw_axis` / `canonical_axis` / `n_member_absent_cells`。
    """
    _win = _window_rows(full)
    _canon, _cmeta = canonicalize_sector_daily(_win)
    _, _raw_meta = compute_bubble(_win)
    bubble, meta = compute_bubble(_canon)
    _members = _cmeta.get("members") or {}
    bubble["members"] = [list(_members.get(str(x), [str(x)])) for x in bubble["sector"]] \
        if not bubble.empty else []
    # 批 Z43 QA2-N4:窗口內「該標準板塊有列、但只出現部分成員標籤」的日數(可追溯;不顯示)
    _mad = _cmeta.get("member_absent_days") or {}
    bubble["n_member_absent_days"] = [int(_mad.get(str(x), 0)) for x in bubble["sector"]] \
        if not bubble.empty else []
    meta["raw_axis"] = _axis_meta(_raw_meta)
    meta["canonical_axis"] = _axis_meta(meta)
    meta["n_member_absent_cells"] = _cmeta.get("n_member_absent_cells")
    _n_used = meta.get("n_trading_days_used") or 0
    _n_tp = meta.get("n_days_tpex_ok")
    meta["tpex_complete"] = bool(_n_tp is not None and _n_used > 0 and _n_tp == _n_used)
    payload = _json_safe({
        "updated_at": pd.Timestamp.now("UTC").isoformat(),
        "window_size": WINDOW_SIZE,
        "n_trading_days_used": meta.get("n_trading_days_used"),
        "n_days_tpex_ok": _n_tp,
        "tpex_complete": meta["tpex_complete"],
        "n_absent_cells": meta.get("n_absent_cells"),
        "sector_aliases_version": SECTOR_ALIASES_VERSION,
        "sectors": bubble.to_dict(orient="records"),
    })
    BUBBLE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2,
                                      allow_nan=False) + "\n",
                           encoding="utf-8")
    print(f"[sector_flow] ✅ bubble_latest.json:{len(bubble)} 板塊 "
          f"({meta.get('n_trading_days_used')} 交易日)")
    return meta


def _clean_industry_map(industry_map: dict | None) -> dict:
    """{代號: 產業別} 去掉代號或產業別為空的髒列(不臆造)。"""
    return {str(k).strip(): str(v).strip() for k, v in (industry_map or {}).items()
            if str(k).strip() and v is not None and str(v).strip()}


def _prev_ticker_sector_count() -> int | None:
    """上一份 ticker_sector.json 的代號數;檔缺 / 壞檔 / 非 dict → None(無從比較)。"""
    if not TICKER_SECTOR_PATH.exists():
        return None
    try:
        _v = json.loads(TICKER_SECTOR_PATH.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001 — 壞檔不得讓 cron 整個炸;印出來
        print(f"[sector_flow] ⚠️ 讀上一份 ticker_sector.json 失敗({type(e).__name__}: {e})")
        return None
    return len(_v) if isinstance(_v, dict) else None


def _industry_map_guard(industry_map: dict | None) -> str | None:
    """批 Z41 修正(QA H1):本次產業別對映不可信 → 回傳原因字串;可信 → None。

    不可信 ＝ 清洗後為空,或代號數相對上一份 `ticker_sector.json` 縮水超過
    `INDUSTRY_MAP_MAX_SHRINK_RATIO`。不可信時 main **禁止改寫任何既有日**(回補全部跳過),
    新日照寫但記 warning + last_error;且不覆寫 ticker_sector.json(保留上一份可信對映,
    否則下一次會拿縮水版當基準而放行)。
    """
    n_now = len(_clean_industry_map(industry_map))
    if n_now == 0:
        return "產業別整表為空(FinMind + openapi 皆敗)"
    n_prev = _prev_ticker_sector_count()
    if n_prev and n_now < n_prev * (1 - INDUSTRY_MAP_MAX_SHRINK_RATIO):
        return (f"產業別代號數 {n_now} 較上一份 ticker_sector.json {n_prev} 縮水 "
                f"{1 - n_now / n_prev:.0%} > {INDUSTRY_MAP_MAX_SHRINK_RATIO:.0%}")
    return None


def _write_ticker_sector_json(industry_map: dict) -> None:
    """多存一份 {裸股號: 產業別} 供 Stage 2 UI 把持股對映板塊(highlight)。

    §1 Fail Loud, Never Fake:industry_map 空(FinMind + openapi 皆敗)→ **不寫**,
    不留一份空表冒充成功;既有(上次成功那份)保留不動。只清洗掉 code/sector 任一為空
    的髒列(不臆造產業別)。
    """
    if not industry_map:
        print("[sector_flow] ⚠️ industry_map 空 → 不寫 ticker_sector.json(§1 不造假,保留既有)")
        return
    clean = {str(k).strip(): str(v).strip()
             for k, v in industry_map.items()
             if str(k).strip() and str(v).strip()}
    if not clean:
        print("[sector_flow] ⚠️ industry_map 清洗後為空 → 不寫 ticker_sector.json")
        return
    TICKER_SECTOR_PATH.write_text(
        json.dumps(clean, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[sector_flow] ✅ ticker_sector.json:{len(clean)} 檔 → {TICKER_SECTOR_PATH}")


def _industry_raw_path() -> Path:
    return CACHE_DIR / INDUSTRY_RAW_NAME


def _load_prev_industry_raw() -> dict | None:
    """上一份 industry_raw.json;缺 / 壞檔 / 非 dict → None(印 log,不讓 cron 炸)。"""
    p = _industry_raw_path()
    if not p.exists():
        return None
    try:
        _v = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001 — 壞檔不得讓 cron 整個炸;印出來
        print(f"[sector_flow] ⚠️ 讀上一份 {INDUSTRY_RAW_NAME} 失敗({type(e).__name__}: {e})")
        return None
    return _v if isinstance(_v, dict) else None


def _resolve_industry(industry_map: dict | None) -> tuple[dict, dict | None, str]:
    """批 Z43:`fetch_industry_map_bulk()` 結果 → (最終 map, 選列紀錄 | None, industry_scheme)。

    - 取 L1 `get_last_industry_raw()`;其扁平 map 須與 `industry_map` 完全相同才採用(防張冠李戴)。
    - 有官方端點失敗的市場 → `apply_prev_chosen` 以上一份 industry_raw 的 chosen 覆蓋該市場代號;
      scheme 加 `INDUSTRY_SCHEME_DEGRADED_SUFFIX`(≠ 現行版本 → 官方恢復後回補重算)。
    - FinMind 失敗(`finmind_status.ok` 為 False)而官方成功 → 同樣加 `INDUSTRY_SCHEME_DEGRADED_SUFFIX`
      (批 Z43 QA1-N3:官方查無者此時無產業別,不只靠縮水守衛;FinMind 恢復後回補重算)。
    - 拿不到對應紀錄(例:測試替身直接給 map)→ map 原樣、不落地 industry_raw、metadata.industry 記
      `raw_available=False` + 警示;scheme 照記現行版本 —— 回補重抓只會得到同一份 map、修不好「紀錄缺」,
      標成過期只會每日空轉(與「官方端點失敗」不同:那種官方恢復後回補就能修好,故加後綴)。
    """
    _map = _clean_industry_map(industry_map)
    raw = get_last_industry_raw()
    if not raw or _clean_industry_map(industry_map_from_raw(raw)) != _map:
        if industry_map:
            print("[sector_flow] ⚠️ 產業別選列紀錄缺或與 map 不符 → 不落地 industry_raw(metadata 記警示)")
        return dict(industry_map or {}), None, INDUSTRY_SCHEME_VERSION
    scheme = INDUSTRY_SCHEME_VERSION
    if raw.get("unavailable_markets"):
        raw = apply_prev_chosen(raw, _load_prev_industry_raw())
        scheme = INDUSTRY_SCHEME_VERSION + INDUSTRY_SCHEME_DEGRADED_SUFFIX
        _n_prev = sum(1 for r in (raw.get("codes") or {}).values()
                      if (r.get("chosen") or {}).get("from_prev"))
        print(f"[sector_flow] ⚠️ 官方產業別端點不可用 {raw['unavailable_markets']} → "
              f"沿用上一份 chosen {_n_prev} 檔;scheme={scheme}")
    if (raw.get("finmind_status") or {}).get("ok") is False:
        scheme = INDUSTRY_SCHEME_VERSION + INDUSTRY_SCHEME_DEGRADED_SUFFIX
        print(f"[sector_flow] ⚠️ FinMind TaiwanStockInfo 失敗 → scheme={scheme}(FinMind 恢復後回補重算)")
    raw["scheme_written"] = scheme
    return industry_map_from_raw(raw), raw, scheme


def _alias_consistency(raw: dict | None) -> dict:
    """批 Z43 QA1-N2:以**當次** industry_raw 的 chosen label × 官方代碼,檢查別名表與官方代碼是否一致。

    回 {"code_to_multi_canonical": {官方代碼: {標準標籤: 檔數}}(同一官方代碼對到 >1 個標準標籤 → 漏收別名),
        "canonical_to_multi_code": {標準標籤: {官方代碼: 檔數}}(同一標準標籤成員分屬 >1 官方代碼 → 誤併)}。
    官方查無(official None / 無代碼)不計。兩者皆空 ＝ 一致。純計算、不改 raw。
    """
    c2l: dict = {}
    l2c: dict = {}
    for rec in ((raw or {}).get("codes") or {}).values():
        lab = ((rec or {}).get("chosen") or {}).get("label")
        code = ((rec or {}).get("official") or {}).get("code")
        if not lab or not code:
            continue
        canon = canonical_sector(lab)
        c2l.setdefault(str(code), {}).setdefault(canon, 0)
        c2l[str(code)][canon] += 1
        l2c.setdefault(canon, {}).setdefault(str(code), 0)
        l2c[canon][str(code)] += 1
    return {"code_to_multi_canonical": {k: v for k, v in sorted(c2l.items()) if len(v) > 1},
            "canonical_to_multi_code": {k: v for k, v in sorted(l2c.items()) if len(v) > 1}}


def _industry_summary(raw: dict | None, scheme: str) -> dict:
    """metadata 用:產業別選列摘要(不含逐檔紀錄;逐檔在 industry_raw.json)。"""
    if not raw:
        return {"scheme": scheme, "raw_available": False,
                "warnings": ["產業別選列紀錄不可用(map 無對應的原始列 / 官方紀錄)→ 本次未落地 "
                             + INDUSTRY_RAW_NAME]}
    _rules: dict = {}
    _prev = 0
    for rec in (raw.get("codes") or {}).values():
        ch = rec.get("chosen") or {}
        _rules[ch.get("rule")] = _rules.get(ch.get("rule"), 0) + 1
        _prev += bool(ch.get("from_prev"))
    _cons = _alias_consistency(raw)
    _warn = list(raw.get("warnings") or [])
    if _cons["code_to_multi_canonical"]:
        _warn.append("別名一致性:同一官方代碼對到多個標準標籤(別名表可能漏收)="
                     + json.dumps(_cons["code_to_multi_canonical"], ensure_ascii=False, sort_keys=True))
    if _cons["canonical_to_multi_code"]:
        _warn.append("別名一致性:同一標準標籤成員分屬多個官方代碼(別名可能誤併)="
                     + json.dumps(_cons["canonical_to_multi_code"], ensure_ascii=False, sort_keys=True))
    return {"scheme": scheme, "raw_available": True, "fetched_at": raw.get("fetched_at"),
            "rules": _rules, "n_from_prev": _prev,
            "official_status": raw.get("official_status"),
            "finmind_status": raw.get("finmind_status"),
            "unavailable_markets": raw.get("unavailable_markets") or [],
            "alias_consistency": _cons,
            "warnings": _warn}


def _write_industry_raw_json(raw: dict | None, scheme: str) -> None:
    """批 Z43:落地完整選列紀錄(原始資料可追溯)。紀錄缺 / codes 空 / **扁平 map 為空**(QA2-N5:例 FinMind 失敗且
    官方代碼皆不在代碼表 → codes 有、但沒有任何 label)→ 不寫(保留上一份,與 ticker_sector.json 同規則,§1)。"""
    if not raw or not raw.get("codes"):
        print(f"[sector_flow] ⚠️ 無產業別選列紀錄 → 不寫 {INDUSTRY_RAW_NAME}(保留既有)")
        return
    if not industry_map_from_raw(raw):
        print(f"[sector_flow] ⚠️ 產業別選列紀錄無任何 label → 不寫 {INDUSTRY_RAW_NAME}(保留既有)")
        return
    _p = _industry_raw_path()
    _p.write_text(json.dumps(_json_safe(raw), ensure_ascii=False, sort_keys=True,
                             separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"[sector_flow] ✅ {INDUSTRY_RAW_NAME}:{len(raw['codes'])} 檔(scheme={scheme})→ {_p}")


def _write_metadata(full: pd.DataFrame, diag: dict, cov: dict,
                    last_error: str | None, bubble_meta: dict | None = None) -> None:
    """批 Z39:追加 per_day / markets_summary / unresolved_days / warnings。

    `warnings` 在「本次有 TPEx 失敗日」「窗口內有交易日未含 TPEx」「有 unresolved 日」時
    非空 —— 不得 last_error=null 又看起來全成功。
    """
    diag = diag or {}
    _summary = _markets_summary(diag)
    _warn: list[str] = []
    if _summary["TPEx"]["fail_days"]:
        _warn.append("本次抓取上櫃(TPEx)未成功日:"
                     + ",".join(_summary["TPEx"]["fail_dates"]) + "(該日只含上市)")
    if diag.get("unresolved_days"):
        _warn.append("上市(TWSE)未成功、未寫入日:" + ",".join(diag["unresolved_days"]))
    if diag.get("industry_map_guard"):
        _warn.append("產業別對映異常 → 本次不改寫任何既有日、回補全部跳過:"
                     + str(diag["industry_map_guard"]))
    for _w in ((diag.get("industry") or {}).get("warnings") or []):
        _warn.append("產業別:" + str(_w))   # 批 Z43:官方端點不可用 / 選列紀錄缺 等
    if diag.get("unresolved_expired"):
        _warn.append("unresolved_expired(超出重抓回溯窗,移出清單):"
                     + ",".join(diag["unresolved_expired"]))
    # 批 Z39 修正(QA N7b):L2 coverage 有法人分項缺值股日 → 結構化警示(該股日 net=NaN、不補 0)
    for _k in ("n_missing_foreign_stock_days", "n_missing_trust_stock_days",
               "n_missing_dealer_stock_days"):
        _n = (cov or {}).get(_k)
        if isinstance(_n, (int, np.integer)) and not isinstance(_n, bool) and _n > 0:
            _warn.append(f"coverage.{_k}={int(_n)}")
    # 批 Z41 修正二(QA R1):窗口內產業別異常期間寫入(industry_ok 明確 False)的日子 → 警示
    if full is not None and not full.empty and "date" in full.columns:
        _win = sorted(pd.to_datetime(full["date"]).dt.normalize().unique())[-int(WINDOW_SIZE):]
        _bad = sorted(pd.Timestamp(x) for x in _industry_bad_dates(full) if pd.Timestamp(x) in set(_win))
        if _bad:
            _warn.append("窗口內產業別異常期間寫入日(全歸未分類,產業別恢復後自動重算):"
                         + ",".join(x.strftime("%Y%m%d") for x in _bad))
    if bubble_meta:
        _n_used = bubble_meta.get("n_trading_days_used") or 0
        _n_tp = bubble_meta.get("n_days_tpex_ok")
        if _n_used and not bubble_meta.get("tpex_complete"):
            _warn.append(f"泡泡圖窗口 {_n_used} 交易日中 TPEx 成功納入 "
                         f"{_n_tp if _n_tp is not None else '未知'} 日 → 目前僅含上市資料")
    payload = {
        "updated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "last_updated": (_last_date(full).isoformat()
                         if _last_date(full) else None),
        "row_count": int(len(full)) if full is not None else 0,
        "n_days": int(pd.to_datetime(full["date"]).dt.normalize().nunique())
                  if full is not None and not full.empty else 0,
        "fetch_diag": {k: v for k, v in diag.items()
                       if k not in ("per_day", "unresolved_days", "tpex_backfill", "industry")},
        "coverage": cov,
        "last_error": last_error,
        "warnings": _warn,
        "per_day": diag.get("per_day") or {},
        "markets_summary": _summary,
        "unresolved_days": list(diag.get("unresolved_days") or []),
        # 批 Z41 R1:本次 TPEx 回補成功(寫入且 tpex_ok=True)的日子 + 回補明細(含 attempted_on 每日一次閘)
        "backfilled_days": list((diag.get("tpex_backfill") or {}).get("backfilled_days") or []),
        "tpex_backfill": diag.get("tpex_backfill"),
        "bubble_window": ({k: bubble_meta.get(k) for k in
                           ("n_trading_days_used", "n_days_tpex_ok", "tpex_complete",
                            "n_absent_cells", "n_missing_value_cells",
                            # 批 Z43:原始軸 / 標準化軸對照(上面幾鍵為標準化軸,即泡泡實際所用)
                            "raw_axis", "canonical_axis", "n_member_absent_cells")}
                          if bubble_meta else None),
        # 批 Z43:板塊名稱標準化版本 + 產業別選列摘要(規則分布 / 官方端點狀態 / scheme)
        "sector_aliases_version": SECTOR_ALIASES_VERSION,
        "industry": diag.get("industry"),
    }
    META_PATH.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2,
                                    allow_nan=False) + "\n",
                         encoding="utf-8")
    print(f"[sector_flow] ✅ metadata.json → {META_PATH}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bootstrap", action="store_true",
                    help="回抓近 --days 日曆日(初次部署 / 補洞用)")
    ap.add_argument("--days", type=int, default=_DEFAULT_BOOTSTRAP_DAYS,
                    help=f"bootstrap 回溯日曆天(預設 {_DEFAULT_BOOTSTRAP_DAYS})")
    args = ap.parse_args(argv)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    today = _today()
    existing = None if args.bootstrap else _load_existing()

    cand = _candidate_trading_days(today, existing, args.bootstrap, args.days)
    # 批 Z39 修正(QA N1):上次 TWSE 未成功、未寫入的日子併入候選重抓(不再永遠跳過)。
    _retry, _expired = _split_retry_unresolved(_load_prev_unresolved(), today)
    cand = sorted(set(cand) | set(_retry))
    # 批 Z41 R1:窗口內 tpex_ok 不為 True 的既有日子併入候選(每日最多一次、上限 25 日)。
    _bf_cands = [] if args.bootstrap else _tpex_backfill_days(existing, today)
    _bf_days: list[_dt.date] = []
    _bf_skip = None
    _bf_on = _load_prev_backfill_attempt()
    if _bf_cands and _bf_on == today.isoformat():
        _bf_skip = f"今日({_bf_on})已回補過一次,不重打"
        print(f"[sector_flow] TPEx 回補略過:{_bf_skip}(候選 {len(_bf_cands)} 日)")
    if _retry:
        print(f"[sector_flow] 重抓上次未解日:{[d.isoformat() for d in _retry]}")
    if not cand and (not _bf_cands or _bf_skip):
        print("[sector_flow] 已是最新,無新交易日待抓")
        # 仍重算 bubble(交易日軸可能因日期前進而右移),但不改長表
        if existing is not None and not existing.empty:
            _write_bubble_json(existing)
        return 0

    # 產業別整表(一次抓,全日共用)
    industry_map = fetch_industry_map_bulk()
    # 批 Z43:取完整選列紀錄 → 官方失敗市場沿用上一份 chosen → 扁平 map;決定本次寫入列的 scheme
    industry_map, _ind_raw, _scheme = _resolve_industry(industry_map)
    if not industry_map:
        # §1:無產業別 → L2 會全歸「未分類」;仍可算「全市場」但失去板塊維度 → loud
        print("[sector_flow] ⚠️ 產業別整表為空,全部將歸『未分類』桶")
    # 批 Z41 修正(QA H1):產業別不可信(空 / 縮水 > 門檻)→ 禁止改寫任何既有日(回補全部跳過,
    # attempted_on 不前進 → 明日再試),新日照寫但記 warning + last_error。⛔ 否則回補會把整窗
    # 改寫成「未分類」且標 tpex_ok=True,之後永不再回補(錯誤資料被永久鎖定)。
    _ind_guard = _industry_map_guard(industry_map)
    if _ind_guard:
        print(f"[sector_flow] ⚠️ 產業別對映異常:{_ind_guard} → 不改寫任何既有日、回補全部跳過")
        if _bf_cands and not _bf_skip:
            _bf_skip = f"產業別對映異常,回補全部跳過(不改寫既有日):{_ind_guard}"
    elif _bf_cands and not _bf_skip:
        _bf_days, _bf_on = list(_bf_cands), today.isoformat()
        cand = sorted(set(cand) | set(_bf_days))
        print(f"[sector_flow] TPEx 回補候選(窗口內 tpex_ok 非 True):"
              f"{[d.isoformat() for d in _bf_days]}")
    if cand:
        print(f"[sector_flow] 抓 {cand[0]} ~ {cand[-1]}(共 {len(cand)} 候選日,"
              f"bootstrap={args.bootstrap})")

    # 持股→板塊對映(Stage 2 UI highlight)**只依賴 industry_map**,與「當日三大法人是否
    # 已公布」完全無關 → 抓到 map 就立刻落地。若擺在後段 happy-path,盤前手動跑(inst 未出)
    # 會走下面 `inst_df.empty` 早退 → ticker_sector.json 永遠不生成(highlight 失效)。
    # 空 map 由 `_write_ticker_sector_json` 內 §1 守衛不寫、保留既有。
    # 批 Z41 修正(QA H1):縮水 map 同樣不寫(保留上一份可信對映;否則明日以縮水版為基準而放行)。
    if _ind_guard and industry_map:
        print("[sector_flow] ⚠️ 產業別對映縮水 → 不覆寫 ticker_sector.json(保留上一份)")
    else:
        _write_ticker_sector_json(industry_map)
        _write_industry_raw_json(_ind_raw, _scheme)   # 批 Z43:與 ticker_sector 同進退

    inst_df, price_df, diag = _collect_days(cand)
    _carry_unresolved(diag, _retry, _expired)
    _settle_backfill(diag, _bf_days, _bf_on, _bf_cands, _bf_skip)
    if _ind_guard:
        diag["industry_map_guard"] = _ind_guard
    diag["industry"] = _industry_summary(_ind_raw, _scheme)
    print(f"[sector_flow] fetch 診斷:{ {k: v for k, v in diag.items() if k != 'industry'} }")
    print(f"[sector_flow] 產業別選列:{diag['industry']}")

    if inst_df.empty:
        msg = "所有候選交易日皆無三大法人資料(假日/來源全敗)"
        if _ind_guard:
            msg = f"產業別對映異常:{_ind_guard}(不改寫既有日);" + msg
        if diag.get("unresolved_days"):
            msg += f";上市(TWSE)未成功日 {','.join(diag['unresolved_days'])} 未寫入"
        print(f"[sector_flow] ❌ {msg} → 不覆寫既有 parquet")
        # 既有存在才重算 bubble;完全無資料 → 非零 exit
        if existing is not None and not existing.empty:
            _bm = _write_bubble_json(existing)
            _write_metadata(existing, diag, {}, last_error=msg, bubble_meta=_bm)
            return 0
        _write_metadata(pd.DataFrame(), diag, {}, last_error=msg)
        return 1

    sector_daily, cov = compute_sector_daily_net(inst_df, price_df, industry_map)
    print(f"[sector_flow] L2 coverage:{cov}")

    if sector_daily.empty:
        msg = ("有三大法人資料但換算後 0 板塊列"
               f"(缺價剔除 {cov.get('n_dropped_missing_price')})")
        print(f"[sector_flow] ❌ {msg} → 不覆寫既有 parquet")
        if existing is not None and not existing.empty:
            _bm = _write_bubble_json(existing)
            _write_metadata(existing, diag, cov, last_error=msg, bubble_meta=_bm)
            return 0
        _write_metadata(pd.DataFrame(), diag, cov, last_error=msg)
        return 1

    # provenance(§2.2 schema-additive)。批 Z39:source 依日只列實際成功的市場;
    # 加 twse_ok / tpex_ok(同日相同)兩欄供 bubble 算 tpex_complete(L2 7 欄不變)。
    sector_daily = sector_daily.copy()
    sector_daily["date"] = (pd.to_datetime(sector_daily["date"]).dt.normalize()
                            .astype("datetime64[ns]"))
    sector_daily = sector_daily.merge(_day_flags_frame(diag), on="date", how="left")
    # 批 Z41 修正二(QA R1):本次產業別是否可信 —— 不可信期間寫入的日子標 False,供之後自動重算
    sector_daily["industry_ok"] = not bool(_ind_guard)
    # 批 Z43:本次產業別取法版本(≠ 現行版本的日子之後會被回補重算)
    sector_daily["industry_scheme"] = _scheme
    sector_daily = _norm_flag_cols(sector_daily)
    sector_daily["fetched_at"] = pd.Timestamp.now("UTC").isoformat()

    # 批 Z41 修正(QA H1):產業別不可信 → 已在檔內的日子一律不改寫(含 bootstrap 模式:以磁碟上的
    # 既有 parquet 為基底,不整檔覆蓋),只寫入真正的新日。
    _last_err = None
    if _ind_guard:
        _last_err = f"產業別對映異常:{_ind_guard};本次不改寫任何既有日、TPEx 回補全部跳過"
        if existing is None:
            existing = _load_existing()
        if existing is not None and not existing.empty:
            _dd = list(set(pd.to_datetime(existing["date"]).dt.normalize()))
            _keep_new = ~sector_daily["date"].isin(_dd)
            if not _keep_new.all():
                print(f"[sector_flow] ⚠️ 產業別異常 → 略過改寫既有日 "
                      f"{int((~_keep_new).sum())} 列")
            sector_daily = sector_daily[_keep_new.to_numpy()]

    # 批 Z41:本次寫入的日子先刪 parquet 中該日所有舊列(不可只靠 (date,sector) keep=last ——
    # 舊板塊列會殘留);未寫入的日子(TWSE 失敗 / 回空)不在 sector_daily → 既有列不動。
    _base = existing
    if existing is not None and not existing.empty:
        _new_dates = set(pd.to_datetime(sector_daily["date"]).dt.normalize())
        _exd = pd.to_datetime(existing["date"]).dt.normalize()
        _replaced = sorted(set(_exd) & _new_dates)
        if _replaced:
            print(f"[sector_flow] 重寫既有日 {len(_replaced)} 日(先刪該日所有舊列):"
                  f"{[pd.Timestamp(x).date().isoformat() for x in _replaced]}")
        _base = existing[~_exd.isin(list(_new_dates)).to_numpy()]
    if sector_daily.empty and _base is not None and not _base.empty:
        full = _base      # 批 Z41 修正(QA H1):沒有可寫的新日 → 長表原封不動
        print("[sector_flow] 無可寫入的新日(既有日不改寫)→ parquet 不變")
    else:
        full = _norm_flag_cols(_merge_dedupe(_base, sector_daily))
        full.to_parquet(PARQUET_PATH, compression="snappy", index=False)
        print(f"[sector_flow] ✅ 寫入 {len(full)} 列 → {PARQUET_PATH}")

    # ticker_sector.json 已於前段 industry_map 抓取後就落地(與 inst 資料解耦),此處不再重寫。
    _bm = _write_bubble_json(full)
    _write_metadata(full, diag, cov, last_error=_last_err, bubble_meta=_bm)
    if diag.get("unresolved_days") or not _bm.get("tpex_complete"):
        print(f"[sector_flow] ⚠️ unresolved_days={diag.get('unresolved_days')} "
              f"tpex_complete={_bm.get('tpex_complete')}(見 metadata warnings)")

    if diag.get("days_missing_price"):
        print(f"[sector_flow] ⚠️ {diag['days_missing_price']} 個交易日收盤全缺"
              f"(該日金額未計,見 metadata)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
