"""test_export_stock_db.py — stock.db 匯出：離線層讀真 parquet + live 轉換/gating（不打網路）。"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import export_stock_db as E  # noqa: E402


def test_fut_oi_rows_dict_to_df():
    # {YYYYMMDD: 淨口} → DataFrame(date, foreign_net_oi_lots)，排序 + 過濾 None/壞 key
    df = E._fut_oi_rows({"20260718": 12480, "20260717": 9800, "bad": 1, "20260716": None})
    assert list(df["date"]) == ["2026-07-17", "2026-07-18"]
    assert list(df["foreign_net_oi_lots"]) == [9800, 12480]


def test_fut_night_rows_picks_active_contract_and_computes_chg():
    from src.data.macro.leading_indicators import _fut_night_rows
    df = pd.DataFrame([
        {"date": "2026-07-18", "trading_session": "position", "close": 22000, "volume": 100000},
        {"date": "2026-07-18", "trading_session": "position", "close": 21500, "volume": 10},   # 遠月→忽略
        {"date": "2026-07-18", "trading_session": "after_market", "close": 22150, "volume": 80000},
        {"date": "2026-07-18", "trading_session": "after_market", "close": 21400, "volume": 5},  # 遠月
    ])
    r = _fut_night_rows(df).iloc[0]
    assert r["date"] == "2026-07-18"
    assert r["night_close"] == 22150.0 and r["day_close"] == 22000.0   # 各時段取量大近月
    assert r["chg_pts"] == 150.0
    assert abs(r["chg_pct"] - (22150 / 22000 - 1) * 100) < 1e-9


def test_fut_night_rows_no_night_or_bad_schema_empty():
    from src.data.macro.leading_indicators import _fut_night_rows
    # 只有日盤（無 after_market）→ 跳過該日
    day_only = pd.DataFrame(
        [{"date": "2026-07-18", "trading_session": "position", "close": 22000, "volume": 100}]
    )
    assert _fut_night_rows(day_only).empty
    assert _fut_night_rows(pd.DataFrame()).empty              # 空
    assert _fut_night_rows(pd.DataFrame([{"x": 1}])).empty    # 欄不齊


def test_durable_export_from_real_parquet(tmp_path):
    """離線 6 表讀 data_cache 真 parquet；無 token → live 表 Fail-Loud 略過。"""
    db = tmp_path / "stock.db"
    res = E.export_all(db, token="")
    for t in ("stock_fundamentals", "market_index", "institutional_flow",
              "margin", "money_supply", "macro_tw_pmi"):
        assert res[t] > 0, f"{t} 應有列"
    assert res["stock_technical"] == -1        # 缺 token → 略過（不造假）
    assert res["monthly_revenue"] == -1
    assert res["macro_tw_signal"] == -1

    conn = sqlite3.connect(str(db))
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "monthly_revenue" not in tables     # 略過 → 不建空表
    assert "stock_technical" not in tables
    cols = [d[1] for d in conn.execute("PRAGMA table_info(stock_fundamentals)")]
    assert {"stock_id", "revenue", "eps", "total_equity"}.issubset(cols)

    # source_health：反映各維成敗（缺 token 的 live 表 → absent；離線表 → ok），不再默默消失
    assert "source_health" in tables
    health = {r[0]: (r[1], r[2]) for r in conn.execute(
        "SELECT field, status, n_rows FROM source_health")}
    assert health["monthly_revenue"][0] == "absent"
    assert health["stock_technical"][0] == "absent"
    assert health["market_index"] == ("ok", res["market_index"])
    conn.close()


def test_health_rows_maps_status_and_schema():
    df = E._health_rows({"market_index": 100, "monthly_revenue": -1, "empty_ok": 0}, "2026-07-22")
    m = {r["field"]: (r["status"], int(r["n_rows"])) for _, r in df.iterrows()}
    assert m["market_index"] == ("ok", 100)
    assert m["monthly_revenue"] == ("absent", 0)     # 缺料 → absent、n_rows 記 0（不造假）
    assert m["empty_ok"] == ("ok", 0)                # 0 列但有寫 → ok
    assert set(df.columns) == set(E._HEALTH_COLS)
    assert (df["as_of"] == "2026-07-22").all()


def test_revenue_rows_drops_na_and_requires_cols():
    df = pd.DataFrame({
        "stock_id": ["2330", "2317"], "date": ["2026-06", "2026-06"],
        "revenue": [1.0, None],
    })
    out = E._revenue_rows(df)
    assert list(out.columns) == ["stock_id", "date", "revenue"]
    assert len(out) == 1                       # None 顯式剔除,不填 0
    with pytest.raises(RuntimeError):
        E._revenue_rows(pd.DataFrame({"x": [1]}))   # 欄位不齊 → raise


def test_signal_row_and_invalid():
    d = {"date_latest": "2026-06", "score_latest": 22, "color_latest": "黃藍",
         "inflection": "⬆ 翻揚", "source": "NDC"}
    row = E._signal_row(d)
    assert row["score"].iloc[0] == 22 and row["color"].iloc[0] == "黃藍"
    with pytest.raises(RuntimeError):
        E._signal_row({"error": "x"})
    with pytest.raises(RuntimeError):
        E._signal_row({"score_latest": None})


def test_technical_row_core_only_df_aligns_schema():
    """只有 date/close 的最小 df → 核心欄齊；加料欄(KD/籌碼/ma60)缺來源 → 誠實 None（不填 0）。"""
    n = 40
    dates = pd.date_range("2026-06-01", periods=n).strftime("%Y-%m-%d")
    close = pd.Series([100 + i * 0.5 + (1.0 if i % 3 == 0 else -0.5) for i in range(n)])
    df = pd.DataFrame({"date": dates, "close": close})
    row = E._technical_row(df, "2330")
    assert row is not None
    assert set(row) == set(E._TECH_COLS)            # 欄位對齊下游 stock_technical
    assert row["stock_id"] == "2330"
    assert isinstance(row["close"], float)
    assert 0.0 <= row["rsi"] <= 100.0               # RSI 值域
    assert row["upper_band"] > row["lower_band"]    # 上軌 > 下軌
    assert row["ma20"] is not None                  # 40 列 → MA20 可算
    assert row["ma60"] is None                      # 僅 40 列 < 60 → 誠實 None
    assert row["kd_k"] is None and row["kd_d"] is None            # 無 high/low → None
    assert row["foreign_net_lots"] is None          # 無籌碼欄 → None（不填 0）
    assert row["total_net_lots"] is None


def test_technical_row_extracts_chip_kd_ma_from_combined_df():
    """含 high/low/MA/籌碼欄的 combined df → KD/均線/籌碼(張)都撈出（重用 SSOT,不重算,保留負號）。"""
    n = 70
    dates = pd.date_range("2026-04-01", periods=n).strftime("%Y-%m-%d")
    close = pd.Series([100 + i * 0.3 for i in range(n)])
    df = pd.DataFrame({
        "date": dates,
        "high": close + 1.0,
        "low": close - 1.0,
        "close": close,
        "MA20": close.rolling(20).mean(),
        "MA60": close.rolling(60).mean(),
        "外資": [None] * (n - 1) + [-115284.0],      # 張(net 賣超為負)
        "投信": [None] * (n - 1) + [739.0],
        "主力合計": [None] * (n - 1) + [-121700.0],  # 三大法人＝外資+投信+自營
    })
    row = E._technical_row(df, "6770")
    assert row["ma20"] is not None and row["ma60"] is not None
    assert row["kd_k"] is not None and 0.0 <= row["kd_k"] <= 100.0
    assert row["foreign_net_lots"] == -115284.0     # 張,保留負號（賣超）
    assert row["trust_net_lots"] == 739.0
    assert row["total_net_lots"] == -121700.0


def test_technical_row_insufficient_data_returns_none():
    df = pd.DataFrame({"date": ["2026-06-01"], "close": [100.0]})   # 只有 1 列 → 不足
    assert E._technical_row(df, "2330") is None


def test_live_gating_skips_without_token(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "x.db"))
    try:
        assert E.write_stock_technical(conn, ["2330"], token="") == -1
        assert E.write_monthly_revenue(conn, token="") == -1
        assert E.write_macro_tw_signal(conn, token="") == -1
    finally:
        conn.close()
