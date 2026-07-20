"""test_export_stock_db.py — stock.db 匯出：離線層讀真 parquet + live 轉換/gating（不打網路）。"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import export_stock_db as E  # noqa: E402


def test_durable_export_from_real_parquet(tmp_path):
    """離線 6 表讀 data_cache 真 parquet；無 token → live 表 Fail-Loud 略過。"""
    db = tmp_path / "stock.db"
    res = E.export_all(db, token="")
    for t in ("stock_fundamentals", "market_index", "institutional_flow",
              "margin", "money_supply", "macro_tw_pmi"):
        assert res[t] > 0, f"{t} 應有列"
    assert res["monthly_revenue"] == -1        # 缺 token → 略過（不造假）
    assert res["macro_tw_signal"] == -1

    conn = sqlite3.connect(str(db))
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "monthly_revenue" not in tables     # 略過 → 不建空表
    cols = [d[1] for d in conn.execute("PRAGMA table_info(stock_fundamentals)")]
    assert {"stock_id", "revenue", "eps", "total_equity"}.issubset(cols)
    conn.close()


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


def test_live_gating_skips_without_token(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "x.db"))
    try:
        assert E.write_monthly_revenue(conn, token="") == -1
        assert E.write_macro_tw_signal(conn, token="") == -1
    finally:
        conn.close()
