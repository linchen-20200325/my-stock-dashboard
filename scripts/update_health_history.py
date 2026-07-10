"""scripts/update_health_history.py — 健康度歷史每日快照(cron CLI,B8 v19.77)。

user 2026-07-10 核准 review B8「repo 快照 + cron」:原健康度走勢只存
st.session_state(App 重啟歸零,趨勢圖累積不起來)。本 script 由 GitHub Actions
於工作日 TW 17:30(UTC 09:30,盤後 TWSE 17:00 資料齊 → §4.5)對
`data_cache/health_watchlist.json` 清單逐檔:

    L1 StockDataLoader.get_combined_data(sid, 360, True)   ← 與 UI/批次同一條抓取線
    → L2 calc_rsi/ibs/volume_ratio/kd/bollinger            ← 與 UI 同一組指標
    → L2 calc_health_score                                  ← 與 UI 同一個 6 因子公式

**零新公式**(SSOT,對齊 scripts/shortage_cli.py 薄殼 driver 精神),單機分數與
網頁保證一致。結果 append 進 `data_cache/health_history.parquet`(冪等:
(date, sid) 重跑覆蓋)+ `health_history_meta.json`(§5 可觀測性)。

§1 Fail Loud:無 token / 清單缺或空 → 顯式訊息 + exit 0(不造假);
個股抓失敗 → 該股當日缺列 + 記入 meta.fails(不填假值)。
§2.3 PIT:date = 該檔最後一根 K 的**交易日**(非執行日) — 連假重跑同鍵覆蓋,不重複。

用法:
    export FINMIND_TOKEN=xxx
    python scripts/update_health_history.py                 # 讀 watchlist
    python scripts/update_health_history.py --stocks 2330,2317   # 臨時指定
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from src.services.health_history_service import (  # noqa: E402 — 路徑常數 SSOT
    HEALTH_HISTORY_META_JSON,
    HEALTH_HISTORY_PARQUET,
    HEALTH_WATCHLIST_JSON,
)

# 與 section_batch_fetcher 相同抓取口徑(360 日 → tail 300;MA 欄在 tail 前已算好,
# 各指標皆為尾端視窗 ≤240,分數與 UI 任一天數選擇(≥250)一致)
_FETCH_DAYS = 360
_TAIL_ROWS = 300


def load_watchlist(path: Path = HEALTH_WATCHLIST_JSON) -> list[str]:
    """讀追蹤清單。檔缺 / 格式錯 / 空清單 → 顯式訊息 + 回 [](§1 不腦補持股)。"""
    if not path.exists():
        print(f"[health-history] ⚠️ 追蹤清單不存在:{path}\n"
              f"  → 請建立 JSON:{{\"stocks\": [\"2330\", \"2317\"]}}(填您要累積走勢的代碼)")
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        stocks = [str(s).strip() for s in (data.get("stocks") or []) if str(s).strip()]
    except Exception as e:
        print(f"[health-history] ❌ 追蹤清單解析失敗:{type(e).__name__}: {e}")
        return []
    if not stocks:
        print(f"[health-history] ℹ️ 追蹤清單為空({path.name} 的 stocks 列表)"
              f" → 無事可做;要累積走勢請填入代碼後 commit")
    return stocks


def compute_health_row(sid: str, loader) -> tuple[dict | None, str | None]:
    """單檔:抓價 → 指標 → 6 因子健康分。回 (row, None) 或 (None, 錯誤訊息)。

    公式完全重用 L2(scoring_helpers.calc_health_score + tech_indicators),
    不在此重寫任何計算(SSOT)。
    """
    from src.compute.scoring import calc_health_score
    from src.compute.strategy import (
        calc_bollinger, calc_ibs, calc_kd, calc_rsi, calc_volume_ratio,
    )

    df_raw, err, _name = loader.get_combined_data(sid, _FETCH_DAYS, True)
    if df_raw is None or df_raw.empty:
        return None, (err or "無 K 線資料(yfinance + FinMind 雙源皆空)")
    df = df_raw.tail(_TAIL_ROWS).reset_index(drop=True)

    rsi = calc_rsi(df)
    ibs = calc_ibs(df)
    vr = calc_volume_ratio(df)
    k, d = calc_kd(df)
    bb = calc_bollinger(df)
    health, _details = calc_health_score(df, rsi, ibs, vr, k, d, bb)

    # §4.2 不變量:健康分 ∈ [0, 100];越界 = 上游公式壞,寧缺勿錯
    if not (0 <= float(health) <= 100):
        return None, f"health={health} 越界 [0,100](§4.2),棄列"

    trade_date = str(df["date"].iloc[-1])[:10] if "date" in df.columns else ""
    if len(trade_date) != 10:
        return None, f"交易日欄異常:{trade_date!r}(§2.3 PIT 鍵缺),棄列"

    import pandas as pd
    return {
        "date": trade_date,                       # PIT 鍵 = 交易日,非執行日
        "sid": str(sid),
        "health": float(health),
        "rsi": (float(rsi) if rsi is not None else None),
        "close": float(df["close"].iloc[-1]),
        "source": "cron:update_health_history",   # §2.2 provenance
        "fetched_at": pd.Timestamp.now("UTC").isoformat(),
    }, None


def merge_and_write(new_rows: list[dict],
                    parquet_path: Path = HEALTH_HISTORY_PARQUET) -> int:
    """冪等合併:(date, sid) 重跑覆蓋(keep='last'),升序寫回。回總列數。"""
    import pandas as pd

    new_df = pd.DataFrame(new_rows)
    if parquet_path.exists():
        try:
            hist = pd.read_parquet(parquet_path)
        except Exception as e:
            # §1:壞檔顯式重建(舊史遺失要看得見),不靜默疊壞資料
            print(f"[health-history] ⚠️ 既有 parquet 讀取失敗,重建新檔"
                  f"(舊歷史遺失!):{type(e).__name__}: {e}")
            hist = pd.DataFrame()
        merged = pd.concat([hist, new_df], ignore_index=True)
    else:
        merged = new_df
    merged = (merged.drop_duplicates(subset=["date", "sid"], keep="last")
                    .sort_values(["sid", "date"]).reset_index(drop=True))
    # §4.2:寫出前不變量(全表)
    assert merged["health"].between(0, 100).all(), "health 越界 [0,100]"
    assert (merged["close"] > 0).all(), "close 應為正"
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(parquet_path, compression="snappy", index=False)
    return len(merged)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="健康度歷史每日快照(B8)")
    ap.add_argument("--stocks", default="",
                    help="逗號分隔代碼,覆蓋 watchlist(測試/回補用)")
    args = ap.parse_args(argv)

    import os
    if not (os.environ.get("FINMIND_TOKEN") or os.environ.get("FM_TOKEN")):
        # 無 token 仍可跑(loader 匿名模式 600 req/hr + yfinance 主線),僅提示
        print("[health-history] ℹ️ 無 FINMIND_TOKEN(匿名模式,額度較低)")

    stocks = ([s.strip() for s in args.stocks.split(",") if s.strip()]
              if args.stocks else load_watchlist())
    if not stocks:
        return 0  # 顯式訊息已印;空清單非錯誤(§1 不腦補)

    from src.data.core import StockDataLoader
    loader = StockDataLoader()

    rows: list[dict] = []
    fails: list[dict] = []
    for sid in stocks:
        try:
            row, err = compute_health_row(sid, loader)
        except Exception as e:  # 單檔炸不連坐(per-stock 隔離)
            row, err = None, f"{type(e).__name__}: {e}"
        if row is not None:
            rows.append(row)
            print(f"[health-history] ✅ {sid} {row['date']} health={row['health']:.0f}")
        else:
            fails.append({"sid": sid, "err": str(err)[:200]})
            print(f"[health-history] ❌ {sid} {err}")

    import pandas as pd
    if rows:
        # 顯式傳 module global(call-time 查找)而非吃函式預設 — 測試可 monkeypatch 路徑
        total = merge_and_write(rows, parquet_path=HEALTH_HISTORY_PARQUET)
    elif HEALTH_HISTORY_PARQUET.exists():
        total = len(pd.read_parquet(HEALTH_HISTORY_PARQUET))  # 全敗:不動舊史,只記 meta
    else:
        total = 0

    # §5 可觀測性:meta(成功/失敗/總列數);失敗清單攤開供診斷
    meta = {
        "updated_at": pd.Timestamp.now("UTC").isoformat(),
        "n_requested": len(stocks), "n_ok": len(rows), "n_fail": len(fails),
        "fails": fails, "rows_total": int(total),
    }
    HEALTH_HISTORY_META_JSON.parent.mkdir(parents=True, exist_ok=True)
    HEALTH_HISTORY_META_JSON.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[health-history] 完成:{len(rows)}/{len(stocks)} 檔入庫,"
          f"累計 {total} 列;失敗 {len(fails)} 檔")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
