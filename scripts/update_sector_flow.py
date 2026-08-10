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
- 走與畫面同源的 L1 fetcher(T86 selectType=ALL / TPEX 3itrade / MI_INDEX / TPEX 收盤)
- 直連即可(fetch_url 內 PROXY_URL 未設自動降級直連,官方 endpoint 全球可達)

§1 Fail Loud, Never Fake
------------------------
- 某交易日**三大法人全空**(假日/來源全敗)→ 該日整日跳過,不寫假(§4.6 自然排除)。
- 某日有法人淨額但**收盤全缺** → L2 inner-join 會剔除該日全部股 + coverage 計數;
  metadata 記 `days_missing_price` 供排查(不補價、不 ffill,§4.6 停牌不可 ffill)。
- **全部交易日皆無有效資料** → 不覆寫既有 parquet + 非零 exit(§1 寧缺勿錯)。
- 冪等(§5):同交易日重跑覆蓋同 (date,sector) 列(dedupe keep='last'),不產重複。

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
import sys
from pathlib import Path

import pandas as pd

# repo root 上 sys.path(同 update_macro_history / update_fundamentals_snapshot 慣例)
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from shared.sector_flow_thresholds import WINDOW_SIZE  # noqa: E402
from src.compute.sector_flow import (  # noqa: E402
    compute_bubble,
    compute_sector_daily_net,
)
from src.data.core.data_loader_inst_fetchers import (  # noqa: E402
    _get_t86_day,
    _get_tpex_day,
)
from src.data.stock.market_close_fetcher import (  # noqa: E402
    fetch_industry_map_bulk,
    fetch_tpex_close_day,
    fetch_twse_close_day,
)

CACHE_DIR = Path("data_cache/sector_flow")
PARQUET_PATH = CACHE_DIR / "daily_net.parquet"
BUBBLE_PATH = CACHE_DIR / "bubble_latest.json"
META_PATH = CACHE_DIR / "metadata.json"

#: bootstrap 預設回溯日曆天(≈ 20 交易日 + 週末/短假緩衝,湊滿 WINDOW_SIZE)。
_DEFAULT_BOOTSTRAP_DAYS = 30
#: 交易日軸鍵。
_DEDUPE_KEYS = ["date", "sector"]


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
    """對每候選日抓 T86+TPEX 法人 + TWSE+TPEX 收盤 → 兩個長表 + 診斷 meta。"""
    inst_rows: list[dict] = []
    price_rows: list[dict] = []
    diag = {"days_fetched": 0, "days_holiday_or_empty": 0, "days_missing_price": 0}
    for d in days:
        ds = d.strftime("%Y%m%d")
        t86 = _get_t86_day(ds) or {}
        tpex = _get_tpex_day(ds) or {}
        if not t86 and not tpex:
            diag["days_holiday_or_empty"] += 1
            continue   # §1/§4.6:全空 = 假日/來源全敗 → 整日跳過,不寫假
        diag["days_fetched"] += 1
        for code, v in {**tpex, **t86}.items():
            inst_rows.append({
                "date": d, "stock_id": str(code).strip(),
                "foreign_lots": v.get("外資", 0.0),
                "trust_lots": v.get("投信", 0.0),
                "dealer_lots": v.get("自營商", 0.0),
            })
        close_map: dict = {}
        close_map.update(fetch_tpex_close_day(ds) or {})
        close_map.update(fetch_twse_close_day(ds) or {})   # 上市覆蓋上櫃(代號不重疊)
        if not close_map:
            # 有法人淨額但當日收盤全缺 → 該日金額無法換算(§1 不補價)
            diag["days_missing_price"] += 1
            print(f"[sector_flow] ⚠️ {ds} 有法人淨額但收盤全缺 → 該日金額不計")
        for code, close in close_map.items():
            price_rows.append({"date": d, "stock_id": str(code).strip(),
                               "close": close})
    inst_df = pd.DataFrame(inst_rows) if inst_rows else pd.DataFrame(
        columns=["date", "stock_id", "foreign_lots", "trust_lots", "dealer_lots"])
    price_df = pd.DataFrame(price_rows) if price_rows else pd.DataFrame(
        columns=["date", "stock_id", "close"])
    return inst_df, price_df, diag


def _write_bubble_json(full: pd.DataFrame) -> dict:
    """由完整長表算最新泡泡座標,落 bubble_latest.json(Stage 2 秒讀)。"""
    bubble, meta = compute_bubble(full)
    payload = {
        "updated_at": pd.Timestamp.now("UTC").isoformat(),
        "window_size": WINDOW_SIZE,
        "n_trading_days_used": meta.get("n_trading_days_used"),
        "sectors": bubble.to_dict(orient="records"),
    }
    BUBBLE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(f"[sector_flow] ✅ bubble_latest.json:{len(bubble)} 板塊 "
          f"({meta.get('n_trading_days_used')} 交易日)")
    return meta


def _write_metadata(full: pd.DataFrame, diag: dict, cov: dict,
                    last_error: str | None) -> None:
    payload = {
        "updated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "last_updated": (_last_date(full).isoformat()
                         if _last_date(full) else None),
        "row_count": int(len(full)) if full is not None else 0,
        "n_days": int(pd.to_datetime(full["date"]).dt.normalize().nunique())
                  if full is not None and not full.empty else 0,
        "fetch_diag": diag,
        "coverage": cov,
        "last_error": last_error,
    }
    META_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
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
    today = _dt.date.today()
    existing = None if args.bootstrap else _load_existing()

    cand = _candidate_trading_days(today, existing, args.bootstrap, args.days)
    if not cand:
        print("[sector_flow] 已是最新,無新交易日待抓")
        # 仍重算 bubble(交易日軸可能因日期前進而右移),但不改長表
        if existing is not None and not existing.empty:
            _write_bubble_json(existing)
        return 0

    print(f"[sector_flow] 抓 {cand[0]} ~ {cand[-1]}(共 {len(cand)} 候選日,"
          f"bootstrap={args.bootstrap})")

    # 產業別整表(一次抓,全日共用)
    industry_map = fetch_industry_map_bulk()
    if not industry_map:
        # §1:無產業別 → L2 會全歸「未分類」;仍可算「全市場」但失去板塊維度 → loud
        print("[sector_flow] ⚠️ 產業別整表為空,全部將歸『未分類』桶")

    inst_df, price_df, diag = _collect_days(cand)
    print(f"[sector_flow] fetch 診斷:{diag}")

    if inst_df.empty:
        msg = "所有候選交易日皆無三大法人資料(假日/來源全敗)"
        print(f"[sector_flow] ❌ {msg} → 不覆寫既有 parquet")
        # 既有存在才重算 bubble;完全無資料 → 非零 exit
        if existing is not None and not existing.empty:
            _write_bubble_json(existing)
            _write_metadata(existing, diag, {}, last_error=msg)
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
            _write_bubble_json(existing)
            _write_metadata(existing, diag, cov, last_error=msg)
            return 0
        _write_metadata(pd.DataFrame(), diag, cov, last_error=msg)
        return 1

    # provenance(§2.2 schema-additive)
    sector_daily = sector_daily.copy()
    sector_daily["source"] = "TWSE:T86+MI_INDEX / TPEX:3itrade+otc_quotes"
    sector_daily["fetched_at"] = pd.Timestamp.now("UTC").isoformat()

    full = _merge_dedupe(existing, sector_daily)
    full.to_parquet(PARQUET_PATH, compression="snappy", index=False)
    print(f"[sector_flow] ✅ 寫入 {len(full)} 列 → {PARQUET_PATH}")

    _write_bubble_json(full)
    _write_metadata(full, diag, cov, last_error=None)

    if diag.get("days_missing_price"):
        print(f"[sector_flow] ⚠️ {diag['days_missing_price']} 個交易日收盤全缺"
              f"(該日金額未計,見 metadata)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
