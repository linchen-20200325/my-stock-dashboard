"""src/services/health_history_service.py — 健康度歷史快照讀取 + 合併(B8 v19.77)。

user 2026-07-10 核准 review B8 選項「repo 快照 + cron」:
`scripts/update_health_history.py`(cron,工作日 TW 17:30)對 watchlist 逐檔算
6 因子健康分(重用 UI 同一條 L1 get_combined_data → L2 calc_health_score 管線,
零新公式)→ 寫 `data_cache/health_history.parquet` 並 commit。本模組是 UI 端的
讀取口(§8.2:L5 透過 L3 取數,不直讀檔案)。

資料流:cron script(寫) → data_cache parquet → 本 service(讀+合併) →
section_kline_chart(L5 渲染)。

parquet schema(§3.1 等效斷言見 script):
    date(str YYYY-MM-DD,交易日=該日最後一根 K,非執行日) / sid(str) /
    health(float 0-100) / rsi(float 0-100 | NaN) / close(float >0) /
    source(str) / fetched_at(str UTC ISO)

§1 失敗降級:檔缺 / 該股無列 / parquet 壞 → 回 [] + stderr log,
UI fallback 回原本「session 內累積」行為,不造假不炸頁。
"""
from __future__ import annotations

import sys
from pathlib import Path

# repo root = 本檔上溯 2 層(src/services/xxx.py → repo/)。免受 CWD 影響
# (對齊 src/data/stock/fundamentals_snapshot_loader.py 既有模式)。
_REPO_ROOT = Path(__file__).resolve().parents[2]
HEALTH_HISTORY_PARQUET = _REPO_ROOT / "data_cache" / "health_history.parquet"
HEALTH_HISTORY_META_JSON = _REPO_ROOT / "data_cache" / "health_history_meta.json"
HEALTH_WATCHLIST_JSON = _REPO_ROOT / "data_cache" / "health_watchlist.json"


def load_health_history(sid: str, days: int = 14) -> list[dict]:
    """讀某檔股票最近 `days` 個交易日的健康度歷史(升序)。

    Returns:
        list[{'date': 'YYYY-MM-DD', 'health': float, 'rsi': float|None,
              'close': float}](升序);無檔 / 無該股 / 讀取失敗 → []
    """
    if not HEALTH_HISTORY_PARQUET.exists():
        return []
    try:
        import pandas as pd
        df = pd.read_parquet(HEALTH_HISTORY_PARQUET)
        sub = df[df["sid"].astype(str) == str(sid)].sort_values("date").tail(days)
        out: list[dict] = []
        for _, r in sub.iterrows():
            _rsi = r.get("rsi")
            out.append({
                "date": str(r["date"])[:10],
                "health": float(r["health"]),
                "rsi": (float(_rsi) if _rsi is not None and pd.notna(_rsi) else None),
                "close": float(r["close"]),
            })
        return out
    except Exception as e:  # §1:壞檔不炸 UI,log 後 fallback session 行為
        print(f"[health_history_service] 讀取 {HEALTH_HISTORY_PARQUET.name} 失敗"
              f"(fallback session 累積): {type(e).__name__}: {e}", file=sys.stderr)
        return []


def merge_score_history(persisted: list[dict], session_rows: list[dict],
                        keep: int = 7) -> list[dict]:
    """cron 快照(底稿)+ session 即時點(盤中,覆蓋同日)→ UI score_hist 格式。

    純函式。persisted 為 load_health_history 輸出(date=YYYY-MM-DD 升序);
    session_rows 為 section_kline_chart 既有格式(date='MM/DD')。
    同一 MM/DD 以 session 為準(盤中即時分數比 cron 收盤快照新);
    keep 窗內(≤14 天)不可能跨年撞 MM/DD。

    Returns:
        [{'date': 'MM/DD', 'health': ..., 'rsi': ..., 'total': 0}] 升序,尾端 keep 筆
    """
    by_date: dict[str, dict] = {}
    for r in persisted:
        _d = str(r.get("date", ""))
        if len(_d) < 10:
            continue  # 非 YYYY-MM-DD 形狀,略過(§1 不猜)
        _key = f"{_d[5:7]}/{_d[8:10]}"
        by_date[_key] = {
            "date": _key,
            "health": r.get("health"),
            "rsi": r.get("rsi") or 0,
            "total": 0,
        }
    for r in session_rows:  # session 覆蓋同日;dict 保留原插入順序(升序不變)
        _key = str(r.get("date", ""))
        if not _key:
            continue
        by_date[_key] = r
    merged = list(by_date.values())
    return merged[-keep:]
