"""test_source_health_as_of.py — `source_health.as_of` 必須是每列自己的資料日期（2026-08-27）。

守的是一個**已實際發生**的錯誤敘述：原本 `_health_rows(result, as_of)` 把
**每一列**的 `as_of` 都填成匯出日 —— 包括那筆 2026-06 的 PMI。
這比不標更糟：它主動宣稱「那是今天的資料」（§1：錯的敘述比沒有敘述更危險）。

⚠️ 本檔每條都設計成「把修正 revert 成單一匯出日戳記就轉紅」。
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "scripts"))
import export_stock_db as E  # noqa: E402

# ══════════════════════════════════════════════════════════════════════
# 問題 2：source_health.as_of 必須是每列自己的資料日期
# ══════════════════════════════════════════════════════════════════════
def test_health_rows_never_stamps_export_date_on_every_row():
    """核心守衛：兩張表資料日期不同 → as_of 就必須不同。

    revert 成舊的 `_health_rows(result, as_of)`（單一匯出日戳全表）→ 本條轉紅。
    """
    rows = E._health_rows(
        {"market_index": 100, "macro_tw_pmi": 1, "monthly_revenue": -1},
        {"market_index": "2026-08-26", "macro_tw_pmi": "2026-06-01",
         "monthly_revenue": None},
    )
    m = {r["field"]: r["as_of"] for _, r in rows.iterrows()}
    assert m["market_index"] == "2026-08-26"
    assert m["macro_tw_pmi"] == "2026-06-01", "6 月的 PMI 不得被標成匯出日"
    assert m["monthly_revenue"] is None, "取不到資料日期 → 留空，絕不填匯出日"
    assert len({v for v in m.values() if v}) == 2, \
        "每列須帶自己的資料日期，不得全表同一個戳記"


def test_health_rows_missing_field_is_unknown_not_today():
    """as_of map 沒登錄的欄位 → unknown（None），不得 fallback 成匯出日。"""
    rows = E._health_rows({"mystery": 5}, {})
    assert rows.iloc[0]["as_of"] is None


def test_table_as_of_reads_real_max_date(tmp_path):
    """as_of 取自**實際落地的資料**，不是任何時鐘。"""
    db = tmp_path / "x.db"
    conn = sqlite3.connect(str(db))
    try:
        pd.DataFrame({"date": ["2026-01-05", "2026-03-09", "2026-02-01"],
                      "v": [1, 2, 3]}).to_sql("t", conn, index=False)
        assert E._table_as_of(conn, "t") == "2026-03-09"
        assert E._table_as_of(conn, "no_such_table") is None      # 缺表 → unknown
        pd.DataFrame({"a": [1]}).to_sql("nodate", conn, index=False)
        assert E._table_as_of(conn, "nodate") is None             # 無 date 欄 → unknown
    finally:
        conn.close()


def test_export_all_health_as_of_is_not_export_date(tmp_path):
    """端到端：跑真匯出，source_health 不得出現「整欄都是今天」。"""
    db = tmp_path / "stock.db"
    E.export_all(db, token="")
    conn = sqlite3.connect(str(db))
    try:
        rows = list(conn.execute("SELECT field, status, as_of FROM source_health"))
    finally:
        conn.close()
    assert rows, "source_health 必須有列"
    today = E._now_tw_date()
    stamped = [f for f, _s, a in rows if a == today]
    assert not stamped, (
        f"下列維度的 as_of 等於匯出日（{today}）—— 這是在宣稱『這是今天的資料』：{stamped}"
    )
    mi = {f: a for f, _s, a in rows}
    assert mi.get("market_index"), "有資料的表必須帶得出真實資料日期"


