"""scripts/update_fundamentals_snapshot.py — 全台股基本面季快照批次抓取(L1 cron CLI)。

全台股基本面選股網 Phase 1b:每季財報公布後,用 MOPS 全市場彙總 bulk fetcher 抓
上市+上櫃「損益表 + 資產負債表」→ merge 成每檔一列 → 存 parquet 凍結快照。
選股網(L3 service)讀此快照跑 4 項基本面初篩,不再即時打 API。

存儲:data_cache/fundamentals/{market}_{roc_year}Q{season}.parquet(子目錄 → git 可追蹤,
不受 data_cache/*.parquet gitignore 影響)+ latest.json 指標(記錄最新季別)。

§1 fail-loud:某市場抓不到 → log + 保留上季 parquet(不覆蓋、不寫空檔);
全部失敗 → exit 1。§5 冪等:同季重跑覆蓋同檔,不產生重複。

用法(GitHub Actions / 本地):
  python scripts/update_fundamentals_snapshot.py                # 自動抓最新已公布季
  python scripts/update_fundamentals_snapshot.py --roc-year 114 --season 4   # 指定季(回補)
  python scripts/update_fundamentals_snapshot.py --markets sii  # 只抓上市
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path

import pandas as pd

# 允許從 repo root 直接跑
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.stock.mops_bulk_fetcher import (  # noqa: E402
    fetch_mops_balance_bulk,
    fetch_mops_income_bulk,
)

CACHE_DIR = Path("data_cache/fundamentals")
ALL_MARKETS = ["sii", "otc"]
_PROV_COLS = ("source", "fetched_at", "market", "roc_year", "season")


def latest_published_quarter(today: _dt.date) -> tuple[int, int]:
    """依台股財報公告截止日,回最新『應已公布』的季 → (民國年, season)。

    Q1(3/31)~5/15、Q2(6/30)~8/14、Q3(9/30)~11/14、Q4 年報(12/31)~次年 3/31。
    """
    y, md = today.year, (today.month, today.day)
    if md >= (11, 14):
        cal_year, season = y, 3
    elif md >= (8, 14):
        cal_year, season = y, 2
    elif md >= (5, 15):
        cal_year, season = y, 1
    elif md >= (3, 31):
        cal_year, season = y - 1, 4      # 去年年報
    else:
        cal_year, season = y - 1, 3      # 年報尚未出 → 去年 Q3
    return cal_year - 1911, season


def _fetch_market(typek: str, roc_year: int, season: int) -> pd.DataFrame:
    """抓單一市場 損益+資產負債 → merge 成每檔一列;任一表空 → 回空(fail-loud)。"""
    inc = fetch_mops_income_bulk(typek, roc_year, season)
    bal = fetch_mops_balance_bulk(typek, roc_year, season)
    if inc.empty or bal.empty:
        print(f"[fundamentals] {typek} 損益空={inc.empty} 資產負債空={bal.empty} → 跳過")
        return pd.DataFrame()
    # balance 的 provenance 欄與 income 重複,merge 前去掉(保留 income 版)
    _bal = bal.drop(columns=[c for c in _PROV_COLS if c in bal.columns], errors="ignore")
    merged = inc.merge(_bal, on="stock_id", how="outer")
    return merged


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--roc-year", type=int, default=None, help="民國年(預設自動最新)")
    ap.add_argument("--season", type=int, default=None, choices=[1, 2, 3, 4])
    ap.add_argument("--markets", default="sii,otc", help="逗號分隔:sii,otc")
    args = ap.parse_args(argv)

    if args.roc_year and args.season:
        roc_year, season = args.roc_year, args.season
    else:
        roc_year, season = latest_published_quarter(_dt.date.today())
    markets = [m.strip() for m in args.markets.split(",") if m.strip() in ALL_MARKETS]

    # 本季 + 去年同季（供三率三升 YoY 比較）；去年同季抓不到不阻擋本季
    prev_year = roc_year - 1
    quarters = [(roc_year, season), (prev_year, season)]
    print(f"[fundamentals] 目標季別:民國{roc_year} 第{season}季（+ 去年同季 民國{prev_year} 供 YoY），市場={markets}")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    wrote_current, total_rows = 0, 0
    for (_ry, _sn) in quarters:
        for typek in markets:
            df = _fetch_market(typek, _ry, _sn)
            if df.empty:
                print(f"[fundamentals] ❌ {typek} 民國{_ry}Q{_sn} 抓取失敗 → 保留舊 parquet(不覆蓋)")
                continue
            path = CACHE_DIR / f"{typek}_{_ry}Q{_sn}.parquet"
            df.to_parquet(path, compression="snappy", index=False)
            print(f"[fundamentals] ✅ {typek} 民國{_ry}Q{_sn}: {len(df)} 檔 → {path}")
            if _ry == roc_year:   # 只有本季計入「成敗」判斷
                wrote_current += 1
                total_rows += len(df)

    if wrote_current == 0:
        print("[fundamentals] ❌ 本季所有市場都失敗,未更新快照")
        return 1

    (CACHE_DIR / "latest.json").write_text(json.dumps({
        "roc_year": roc_year, "season": season,
        "prev_roc_year": prev_year,   # 去年同季(三率三升 YoY 用)
        "markets_written": wrote_current, "total_rows": total_rows,
        "updated_at": pd.Timestamp.now("UTC").isoformat(),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[fundamentals] 完成:本季 {wrote_current}/{len(markets)} 市場、共 {total_rows} 檔（+ 去年同季 YoY）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
