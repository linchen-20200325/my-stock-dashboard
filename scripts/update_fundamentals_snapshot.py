"""scripts/update_fundamentals_snapshot.py — 全台股基本面季快照批次抓取(L1 cron CLI)。

全台股基本面選股網 Phase 1b:每季財報公布後,用 MOPS 全市場彙總 bulk fetcher 抓
上市+上櫃「損益表 + 資產負債表」→ merge 成每檔一列 → 存 parquet 凍結快照。
選股網(L3 service)讀此快照跑 4 項基本面初篩,不再即時打 API。

存儲:data_cache/fundamentals/{market}_{roc_year}Q{season}.parquet(子目錄 → git 可追蹤,
不受 data_cache/*.parquet gitignore 影響)+ latest.json 指標(記錄最新季別)。

§1 fail-loud:某市場抓不到 → log + 保留上季 parquet(不覆蓋、不寫空檔);
全部失敗 → exit 1。§5 冪等:同季重跑覆蓋同檔,不產生重複。

用法(GitHub Actions / 本地):
  python scripts/update_fundamentals_snapshot.py                       # 自動:本季 + 去年同季(缺才補)
  python scripts/update_fundamentals_snapshot.py --roc-year 114 --season 1      # 回補單季
  python scripts/update_fundamentals_snapshot.py --roc-year 114 --season 2,3,4  # 一次回補多季
  python scripts/update_fundamentals_snapshot.py --markets sii         # 只抓上市

抓幾季:自動模式抓「本季 + 去年同季(YoY 用)」,但去年同季已在快取就略過;手動指定
--roc-year/--season 則『只抓那些季』(回補用,不連去年一起抓)。--season 可逗號分隔多季
(如 2,3,4)一次補齊。latest.json 由磁碟實況重算,補舊季不會把最新指標往回移。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
from pathlib import Path

import pandas as pd

# 允許從 repo root 直接跑
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.roc_calendar import gregorian_to_roc_year  # noqa: E402  B3 SSOT-H2:西元→民國

from src.data.stock.mops_bulk_fetcher import (  # noqa: E402
    fetch_mops_balance_bulk,
    fetch_mops_income_bulk,
)

CACHE_DIR = Path("data_cache/fundamentals")
ALL_MARKETS = ["sii", "otc"]
_PROV_COLS = ("source", "fetched_at", "market", "roc_year", "season")
_FNAME_RE = re.compile(r"^(?:sii|otc)_(\d+)Q(\d)\.parquet$")


def _scan_cached_quarters(cache_dir: Path) -> set[tuple[int, int]]:
    """掃 data_cache/fundamentals/ 下已存在的 parquet → {(民國年, season)} 集合。"""
    out: set[tuple[int, int]] = set()
    for p in cache_dir.glob("*.parquet"):
        m = _FNAME_RE.match(p.name)
        if m:
            out.add((int(m.group(1)), int(m.group(2))))
    return out


def _count_quarter(cache_dir: Path, roc_year: int, season: int) -> tuple[dict, int]:
    """數某季各市場檔數 → ({sii: n, otc: m}, total)。缺檔略過(不列入 dict)。"""
    per: dict[str, int] = {}
    for m in ALL_MARKETS:
        path = cache_dir / f"{m}_{roc_year}Q{season}.parquet"
        if not path.exists():
            continue
        try:
            n = len(pd.read_parquet(path, columns=["stock_id"]))
        except Exception:                             # columns 不符 → 整檔讀
            n = len(pd.read_parquet(path))
        per[m] = n
    return per, sum(per.values())


def _write_latest_json(cache_dir: Path) -> tuple[int, int] | None:
    """由『磁碟實況』重算 latest.json:latest = 現存最新季,prev = 該季去年同季(存在才填)。

    補抓舊季(如 114Q1)不會把 latest 指標往回移;補齊去年同季後 prev 自動補上。
    v19.71:額外寫 coverage(涵蓋率診斷 §5):本季各市場檔數 + total + 去年同季 total(比較基準)。
    回傳 (roc_year, season) 供 log;無任何 parquet 回 None。
    """
    quarters = _scan_cached_quarters(cache_dir)
    if not quarters:
        return None
    roc_year, season = max(quarters)                 # tuple 比較 = 先比年再比季
    prev_available = (roc_year - 1, season) in quarters
    _per, _total = _count_quarter(cache_dir, roc_year, season)
    _prev_total = _count_quarter(cache_dir, roc_year - 1, season)[1] if prev_available else None
    (cache_dir / "latest.json").write_text(json.dumps({
        "roc_year": roc_year, "season": season,
        "prev_roc_year": (roc_year - 1) if prev_available else None,  # YoY 可用才填
        "updated_at": pd.Timestamp.now("UTC").isoformat(),
        "coverage": {                                # §5 涵蓋率診斷(慢公布可見度)
            "sii": _per.get("sii"), "otc": _per.get("otc"),
            "total": _total, "prev_total": _prev_total,
        },
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return roc_year, season


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
    return gregorian_to_roc_year(cal_year), season


def _parse_seasons(raw: str | None) -> list[int]:
    """'2' → [2];'2,3,4' → [2,3,4];'1,2,3,4' → 全年。驗證 ∈{1,2,3,4}、去重保序。

    空/None → []。含非法值 raise ValueError(fail-loud,不靜默吞)。
    """
    if raw is None or str(raw).strip() == "":
        return []
    out: list[int] = []
    for tok in str(raw).split(","):
        tok = tok.strip()
        if not tok:
            continue
        v = int(tok)                       # 非數字 → ValueError
        if v not in (1, 2, 3, 4):
            raise ValueError(f"season 超出範圍:{v}(需 1-4)")
        if v not in out:
            out.append(v)
    return out


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
    ap.add_argument("--season", type=str, default=None,
                    help="季別 1-4;可逗號分隔多季回補,如 2,3,4 或 1,2,3,4(留空=自動最新季)")
    ap.add_argument("--markets", default="sii,otc", help="逗號分隔:sii,otc")
    args = ap.parse_args(argv)

    seasons = _parse_seasons(args.season)
    manual = bool(args.roc_year and seasons)
    markets = [m.strip() for m in args.markets.split(",") if m.strip() in ALL_MARKETS]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # 抓哪幾季:
    #  - 手動指定季別 → 只抓那些季（回補用,不連去年同季;支援多季一次補,如 114 的 2,3,4）
    #  - 自動最新季   → 抓本季 + 去年同季（供三率三升 YoY）;但去年同季若『已在快取』就略過,
    #                   避免每季 cron 都重抓一次舊資料（§5 冪等 + 省時）
    if manual:
        roc_year = args.roc_year
        primary = [(roc_year, s) for s in seasons]   # 這些季全算「主要目標」
        fetch_quarters = list(primary)
        _sn_txt = "、".join(f"Q{s}" for s in seasons)
        print(f"[fundamentals] 手動回補:民國{roc_year} {_sn_txt}(共 {len(seasons)} 季),市場={markets}")
    else:
        roc_year, season = latest_published_quarter(_dt.date.today())
        primary = [(roc_year, season)]
        fetch_quarters = list(primary)
        prev_year = roc_year - 1
        prev_cached = all(
            (CACHE_DIR / f"{m}_{prev_year}Q{season}.parquet").exists() for m in markets
        )
        if prev_cached:
            print(f"[fundamentals] 目標季別:民國{roc_year} 第{season}季,市場={markets}"
                  f"（去年同季 民國{prev_year} 已在快取 → 略過,省時）")
        else:
            fetch_quarters.append((prev_year, season))
            print(f"[fundamentals] 目標季別:民國{roc_year} 第{season}季（+ 去年同季 民國{prev_year} 供 YoY,"
                  f"快取缺 → 一併補抓）,市場={markets}")

    primary_set = set(primary)
    wrote_primary, total_rows = 0, 0
    for (_ry, _sn) in fetch_quarters:
        for typek in markets:
            df = _fetch_market(typek, _ry, _sn)
            if df.empty:
                print(f"[fundamentals] ❌ {typek} 民國{_ry}Q{_sn} 抓取失敗 → 保留舊 parquet(不覆蓋)")
                continue
            path = CACHE_DIR / f"{typek}_{_ry}Q{_sn}.parquet"
            df.to_parquet(path, compression="snappy", index=False)
            print(f"[fundamentals] ✅ {typek} 民國{_ry}Q{_sn}: {len(df)} 檔 → {path}")
            if (_ry, _sn) in primary_set:   # 主要目標季才計入成敗判斷
                wrote_primary += 1
                total_rows += len(df)

    if wrote_primary == 0:
        print("[fundamentals] ❌ 所有主要目標季/市場都失敗,未更新指標")
        return 1

    # latest.json 由磁碟實況重算(補舊季不會把指標往回移;prev 存在才標 YoY 可用)
    latest = _write_latest_json(CACHE_DIR)
    print(f"[fundamentals] 完成:成功寫入 {wrote_primary} 個(市場×季)、共 {total_rows} 檔"
          f"；latest.json 指向 {latest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
