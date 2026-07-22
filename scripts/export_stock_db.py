#!/usr/bin/env python3
"""export_stock_db.py — 把 my-stock 的重點分析資料落地成 SQLite stock.db。

供下游 2026_strategy_0719 多智能體系統讀取。「各源專案各自 export」架構(SSOT):
抓取 / 評分 / 財報邏輯留在本專案,export 只**呼叫既有函式或讀既有 parquet,不重算**。

資料分兩層(對照盤點):
* 🟢 離線層（讀 `data_cache/` parquet/json,**免 API key、免網路**）
    - `stock_fundamentals`  全市場季財報（load_fundamentals_snapshot）
    - `market_index`        加權指數日K（twii_ohlcv.parquet）
    - `institutional_flow`  外資買賣超（finmind_inst.parquet,單位 億元）
    - `margin`              融資餘額（finmind_margin.parquet）
    - `money_supply`        M1B/M2 月供給（finmind_m1m2.parquet,億元 level + gap 點差）
    - `macro_tw_pmi`        台灣 PMI 最後良值（macro_last_good/tw_pmi.json）
* 🔴 live 層（需 `FINMIND_TOKEN`；**缺 token → Fail-Loud 略過該表 + 警告,不造假**）
    - `stock_technical`     個股 close/RSI/布林軌/均線(MA20,60)/KD/逐檔籌碼(外資,投信,三大法人 張)
                            （下游 2026 個股盯盤卡的主要輸入;全部重用 SSOT 指標函式
                            compute_rsi / calc_bollinger / calc_kd / calc_ma_series +
                            get_combined_data 既有欄,不重算。STOCK_IDS 指定個股清單）
    - `monthly_revenue`     全市場月營收（fetch_batch_monthly_revenue,單位 元）
    - `macro_tw_signal`     景氣對策信號燈號（fetch_ndc_signal_history）
    - `futures_oi`          台指期外資留倉淨口數（finmind_fut_oi,單位 口;+多/-空）
    - `futures_night`       台指期日盤+夜盤收盤 → 夜盤漲跌（finmind_fut_night;盤前隔日開盤領先）
* 🩺 健康表（每次 export 依上述各表成敗自動產生,不需外部抓取）
    - `source_health`       各表 status（ok/absent）+ n_rows + as_of（下游 2026 顯示維度降級/缺料,不再默默消失）

（`stock_health`（MJ 財報評級）為下一增量,需財報體檢管線,另接。）

用法:
    STOCK_DB=/volume1/data/stock.db python scripts/export_stock_db.py
    （不設 STOCK_DB → 寫本專案根目錄 stock.db）

單位鐵則(對照 CLAUDE.md §4.1):財報欄=千元、eps=元、外資/M1B2=億元、月營收=元、PMI=指數。
Fail-Loud:離線層任一表讀不到 → raise;live 層缺 token / 抓不到 → 略過該表 + 警告(不寫假值)。
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

# 專案根（scripts/ 的上一層）；讓 `python scripts/export_stock_db.py` 找得到 src、data_cache。
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
_DATA_CACHE = _ROOT / "data_cache"

# TW 時區（UTC+8）—— source_health as_of 戳記用（對照 CLAUDE.md §4.5：TW 時間一律 std datetime）。
_TW_TZ = timezone(timedelta(hours=8))


def _now_tw_date() -> str:
    return datetime.now(_TW_TZ).date().isoformat()


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


# ── 🟢 離線層（讀 parquet/json，免 key） ─────────────────────────────────────
_FUND_COLS = [
    "stock_id", "roc_year", "season", "revenue", "gross_profit", "op_income",
    "net_income", "eps", "total_assets", "total_liab", "current_assets",
    "total_equity", "market",
]


def write_fundamentals(conn: sqlite3.Connection) -> int:
    """全市場最新季財報 → stock_fundamentals（呼叫既有 loader,不重算）。"""
    from src.data.stock.fundamentals_snapshot_loader import load_fundamentals_snapshot

    cur, _prev, _meta = load_fundamentals_snapshot()
    if cur is None or cur.empty:
        raise RuntimeError("財報快照為空（load_fundamentals_snapshot）→ 拒絕寫空表")
    df = cur[[c for c in _FUND_COLS if c in cur.columns]].copy()
    df.to_sql("stock_fundamentals", conn, if_exists="replace", index=False)
    return len(df)


def _read_cache_parquet(name: str, cols: list[str]) -> pd.DataFrame:
    path = _DATA_CACHE / f"{name}.parquet"
    if not path.exists():
        raise RuntimeError(f"離線快取不存在:{path}（請先在 my-stock 跑 update_macro_history）")
    df = pd.read_parquet(path)
    keep = [c for c in cols if c in df.columns]
    return df[keep].copy()


def write_market_index(conn: sqlite3.Connection) -> int:
    df = _read_cache_parquet("twii_ohlcv", ["date", "open", "high", "low", "close", "volume"])
    df.to_sql("market_index", conn, if_exists="replace", index=False)
    return len(df)


def write_institutional_flow(conn: sqlite3.Connection) -> int:
    # foreign_buy 單位 億元（net）；投信/自營未落地,故僅外資。
    df = _read_cache_parquet("finmind_inst", ["date", "foreign_buy"])
    df.to_sql("institutional_flow", conn, if_exists="replace", index=False)
    return len(df)


def write_margin(conn: sqlite3.Connection) -> int:
    df = _read_cache_parquet("finmind_margin", ["date", "margin_balance"])
    df.to_sql("margin", conn, if_exists="replace", index=False)
    return len(df)


def write_money_supply(conn: sqlite3.Connection) -> int:
    df = _read_cache_parquet("finmind_m1m2", ["date", "m1b", "m2", "m1b_m2_gap"])
    df.to_sql("money_supply", conn, if_exists="replace", index=False)
    return len(df)


def write_macro_tw_pmi(conn: sqlite3.Connection) -> int:
    import json

    path = _DATA_CACHE / "macro_last_good" / "tw_pmi.json"
    if not path.exists():
        raise RuntimeError(f"台灣 PMI 良值檔不存在:{path}")
    d = json.loads(path.read_text(encoding="utf-8"))
    df = pd.DataFrame([{
        "date": d.get("date"), "pmi": d.get("value"),
        "label": d.get("label"), "source": d.get("source"),
    }])
    df.to_sql("macro_tw_pmi", conn, if_exists="replace", index=False)
    return len(df)


# ── 🔴 live 層（需 FINMIND_TOKEN；pure transform 抽出以利單測） ────────────────
def _revenue_rows(df: pd.DataFrame) -> pd.DataFrame:
    """全市場月營收 DataFrame → 落地欄位（純轉換,無 I/O,便於單測）。"""
    cols = [c for c in ["stock_id", "date", "revenue"] if c in df.columns]
    if not {"stock_id", "date", "revenue"}.issubset(df.columns):
        raise RuntimeError(f"月營收欄位不齊:{list(df.columns)}")
    out = df[cols].copy()
    out = out[out["revenue"].notna()]     # 缺值顯式剔除,不填 0（§1 Fail-Loud）
    return out


def _fut_oi_rows(oi: dict) -> pd.DataFrame:
    """finmind_fut_oi dict {YYYYMMDD: 淨口} → DataFrame(date=YYYY-MM-DD, foreign_net_oi_lots)（純轉換）。"""
    rows = [
        {"date": f"{k[:4]}-{k[4:6]}-{k[6:8]}", "foreign_net_oi_lots": v}
        for k, v in sorted(oi.items())
        if v is not None and len(str(k)) == 8
    ]
    return pd.DataFrame(rows, columns=["date", "foreign_net_oi_lots"])


def write_futures_oi(conn: sqlite3.Connection, token: str) -> int:
    """台指期外資留倉 → futures_oi（缺 token → 略過 + 警告）。"""
    if not token:
        _log("⚠️ 略過 futures_oi：未設 FINMIND_TOKEN（不造假）")
        return -1
    from datetime import datetime, timedelta

    from src.data.macro.leading_indicators import finmind_fut_oi

    end = datetime.now()
    start = end - timedelta(days=120)
    oi = finmind_fut_oi(start.strftime("%Y%m%d"), end.strftime("%Y%m%d"), token)
    if not oi:
        _log("⚠️ 略過 futures_oi：fetch 回空（不寫空表）")
        return -1
    rows = _fut_oi_rows(oi)
    rows.to_sql("futures_oi", conn, if_exists="replace", index=False)
    return len(rows)


def write_futures_night(conn: sqlite3.Connection, token: str) -> int:
    """台指期夜盤漲跌 → futures_night（缺 token → 略過 + 警告）。"""
    if not token:
        _log("⚠️ 略過 futures_night：未設 FINMIND_TOKEN（不造假）")
        return -1
    from datetime import datetime, timedelta

    from src.data.macro.leading_indicators import finmind_fut_night

    end = datetime.now()
    start = end - timedelta(days=120)
    df = finmind_fut_night(start.strftime("%Y%m%d"), end.strftime("%Y%m%d"), token)
    if df is None or df.empty:
        _log("⚠️ 略過 futures_night：fetch 回空（不寫空表）")
        return -1
    df.to_sql("futures_night", conn, if_exists="replace", index=False)
    return len(df)


def write_monthly_revenue(conn: sqlite3.Connection, token: str) -> int:
    """全市場月營收 → monthly_revenue（缺 token → 略過 + 警告）。"""
    if not token:
        _log("⚠️ 略過 monthly_revenue：未設 FINMIND_TOKEN（不造假）")
        return -1
    from src.data.stock.monthly_revenue_fetcher import fetch_batch_monthly_revenue

    df = fetch_batch_monthly_revenue()
    if df is None or df.empty:
        _log("⚠️ 略過 monthly_revenue：fetch 回空（不寫空表）")
        return -1
    rows = _revenue_rows(df)
    rows.to_sql("monthly_revenue", conn, if_exists="replace", index=False)
    return len(rows)


_DEFAULT_STOCK_IDS = ["2330", "2317", "2454", "2308", "2412", "2882", "0050", "0056"]


# stock_technical 落地欄序（SSOT for 本表 schema；下游 2026 `_fetch_technical` 對齊此清單）。
_TECH_COLS = [
    "date", "stock_id", "close", "rsi", "upper_band", "lower_band",
    "ma20", "ma60", "kd_k", "kd_d",
    "foreign_net_lots", "trust_net_lots", "total_net_lots",
]


def _technical_row(df: pd.DataFrame, stock_id: str):
    """個股日K df → dict（欄位見 `_TECH_COLS`）；**核心**(close/rsi/布林)不足 → 回 None。

    對齊下游 2026 `stock_technical` schema。**全部重用本專案 SSOT 指標函式,不重算**：
    RSI=compute_rsi、布林軌=calc_bollinger、KD=calc_kd、均線優先取 get_combined_data 既算好的
    MA20/MA60 欄（缺→calc_ma_series 補算）。籌碼(外資/投信/主力合計＝三大法人,單位 **張**)取自
    get_combined_data 既有欄；缺欄 → None（§1 不捏造,不填 0）。

    分層：核心欄缺 → 整檔回 None（該股略過）；加料欄(KD/均線/籌碼)個別缺 → 該欄 None。
    """
    from src.compute.scoring.scoring_engine import compute_rsi
    from src.compute.strategy.tech_indicators import calc_bollinger, calc_kd, calc_ma_series

    if df is None or df.empty or "close" not in df.columns:
        return None
    bb = calc_bollinger(df, 20, 2)          # {'upper','lower',...};資料不足回 None
    if bb is None:
        return None
    rsi = compute_rsi(df["close"], 14).iloc[-1]
    if pd.isna(rsi):
        return None
    date = str(df["date"].iloc[-1])[:10] if "date" in df.columns else None

    def _last(col: str):
        """某欄最後一個值（缺欄或 NaN → None,不填 0）。"""
        if col not in df.columns:
            return None
        v = df[col].iloc[-1]
        return None if pd.isna(v) else float(v)

    # 均線(元)：優先用 get_combined_data 既算好的 MA20/MA60（SSOT）,缺欄 → calc_ma_series 補
    ma20 = _last("MA20")
    if ma20 is None:
        v = calc_ma_series(df["close"], 20).iloc[-1]
        ma20 = None if pd.isna(v) else float(v)
    ma60 = _last("MA60")
    if ma60 is None:
        v = calc_ma_series(df["close"], 60).iloc[-1]
        ma60 = None if pd.isna(v) else float(v)

    # KD(0~100 無單位)：需 high/low/close;缺欄 → None（不捏造）
    kd_k = kd_d = None
    if {"high", "low", "close"}.issubset(df.columns):
        k, d = calc_kd(df)                   # calc_kd(df, period=9) → (k,d) 或 (None,None)
        kd_k = None if k is None else float(k)
        kd_d = None if d is None else float(d)

    return {
        "date": date,
        "stock_id": stock_id,
        "close": float(df["close"].iloc[-1]),
        "rsi": float(rsi),
        "upper_band": bb["upper"],
        "lower_band": bb["lower"],
        "ma20": ma20,
        "ma60": ma60,
        "kd_k": kd_k,
        "kd_d": kd_d,
        "foreign_net_lots": _last("外資"),    # 張(net;賣超為負)
        "trust_net_lots": _last("投信"),      # 張
        "total_net_lots": _last("主力合計"),  # 張(三大法人＝外資+投信+自營)
    }


def write_stock_technical(conn: sqlite3.Connection, stock_ids: list[str], token: str) -> int:
    """個股技術面 → stock_technical（下游個股分析的主要輸入；缺 token → 略過 + 警告）。"""
    if not token:
        _log("⚠️ 略過 stock_technical：未設 FINMIND_TOKEN（不造假）")
        return -1
    from src.data.core.data_loader import StockDataLoader

    loader = StockDataLoader()
    rows = []
    for sid in stock_ids:
        df, err, _name = loader.get_combined_data(sid, days=250)
        if df is None:
            _log(f"  stock_technical：{sid} 無資料（{err}）跳過")
            continue
        row = _technical_row(df, sid)
        if row is not None:
            rows.append(row)
    if not rows:
        _log("⚠️ 略過 stock_technical：所有個股皆無有效資料（不寫空表）")
        return -1
    # columns=_TECH_COLS：固定欄序（dict → 表），下游 2026 對齊此清單。
    pd.DataFrame(rows, columns=_TECH_COLS).to_sql(
        "stock_technical", conn, if_exists="replace", index=False
    )
    return len(rows)


def _signal_row(d: dict) -> pd.DataFrame:
    """景氣燈號 dict → 一列落地（純轉換）。"""
    if not d or d.get("error") or d.get("score_latest") is None:
        raise RuntimeError(f"景氣燈號無效:{d}")
    return pd.DataFrame([{
        "date": d.get("date_latest"),
        "score": d.get("score_latest"),          # 9~45 分
        "color": d.get("color_latest"),          # 官方燈號
        "trend": d.get("inflection"),
        "source": d.get("source"),
    }])


def write_macro_tw_signal(conn: sqlite3.Connection, token: str) -> int:
    """台灣景氣對策信號 → macro_tw_signal（缺 token → 略過 + 警告）。"""
    if not token:
        _log("⚠️ 略過 macro_tw_signal：未設 FINMIND_TOKEN（不造假）")
        return -1
    from src.data.macro.tw_macro import fetch_ndc_signal_history

    d = fetch_ndc_signal_history(token=token)
    if not d or d.get("error"):
        _log(f"⚠️ 略過 macro_tw_signal：{d.get('error') if d else 'None'}")
        return -1
    _signal_row(d).to_sql("macro_tw_signal", conn, if_exists="replace", index=False)
    return 1


# ── source_health：讓「維度降級 / 缺料」看得見（下游 2026 顯示，不再默默消失） ──
_HEALTH_COLS = ["field", "status", "n_rows", "as_of"]
_HEALTH_OK = "ok"
_HEALTH_ABSENT = "absent"        # 缺 token / 抓不到 → 該表未寫


def _health_rows(result: dict[str, int], as_of: str) -> pd.DataFrame:
    """export result dict → source_health 落地（純轉換，無 I/O，便於單測）。

    status：n < 0（略過 / 缺料）→ absent；否則 ok。n_rows：實際落地列數（absent 記 0）。
    """
    rows = [
        {
            "field": field,
            "status": _HEALTH_ABSENT if n < 0 else _HEALTH_OK,
            "n_rows": max(n, 0),
            "as_of": as_of,
        }
        for field, n in result.items()
    ]
    return pd.DataFrame(rows, columns=_HEALTH_COLS)


def write_source_health(conn: sqlite3.Connection, result: dict[str, int], as_of: str) -> int:
    """各表成敗（ok / absent）落地成 source_health，供下游 2026 顯示『維度降級 / 缺料』。"""
    _health_rows(result, as_of).to_sql("source_health", conn, if_exists="replace", index=False)
    return len(result)


# ── 主流程 ───────────────────────────────────────────────────────────────────
_DURABLE = [
    ("stock_fundamentals", write_fundamentals),
    ("market_index", write_market_index),
    ("institutional_flow", write_institutional_flow),
    ("margin", write_margin),
    ("money_supply", write_money_supply),
    ("macro_tw_pmi", write_macro_tw_pmi),
]


def export_all(db_path: Path, token: str, stock_ids: list[str] | None = None) -> dict[str, int]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    result: dict[str, int] = {}
    try:
        for name, fn in _DURABLE:                 # 離線層：任一失敗即 raise（Fail-Loud）
            result[name] = fn(conn)
        result["stock_technical"] = write_stock_technical(
            conn, stock_ids or _DEFAULT_STOCK_IDS, token
        )
        result["monthly_revenue"] = write_monthly_revenue(conn, token)
        result["macro_tw_signal"] = write_macro_tw_signal(conn, token)
        result["futures_oi"] = write_futures_oi(conn, token)
        result["futures_night"] = write_futures_night(conn, token)
        write_source_health(conn, result, _now_tw_date())
        conn.commit()
    finally:
        conn.close()
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="產生 stock.db 供多智能體系統讀取")
    parser.add_argument("--output", help="stock.db 路徑（預設 env STOCK_DB 或 ./stock.db）")
    args = parser.parse_args(argv)

    out = Path(args.output or os.environ.get("STOCK_DB") or "stock.db")
    token = os.environ.get("FINMIND_TOKEN", "")
    ids = [s.strip() for s in os.environ.get("STOCK_IDS", "").split(",") if s.strip()]
    result = export_all(out, token, ids or None)

    print(f"✅ stock.db 已更新 → {out}")
    for name, n in result.items():
        print(f"   {name}: {'略過(缺 token/資料)' if n < 0 else f'{n} 列'}")
    absent = [name for name, n in result.items() if n < 0]
    if absent:
        print(f"🩺 source_health：{len(absent)} 維缺料 → {', '.join(absent)}（下游 2026 會標降級）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
