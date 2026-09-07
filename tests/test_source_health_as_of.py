"""test_source_health_as_of.py — `source_health.as_of` 必須是每列自己的資料日期（2026-08-27）。

守的是一個**已實際發生**的錯誤敘述：原本 `_health_rows(result, as_of)` 把
**每一列**的 `as_of` 都填成匯出日 —— 包括那筆 2026-06 的 PMI。
這比不標更糟：它主動宣稱「那是今天的資料」（§1：錯的敘述比沒有敘述更危險）。

⚠️ 本檔每條都設計成「把修正 revert 成單一匯出日戳記就轉紅」。

──────────────────────────────────────────────────────────────────────────────
2026-09-07 判準修正（端到端那條）—— 代理判準 → 因果直驗
──────────────────────────────────────────────────────────────────────────────
**舊判準**：`as_of != 匯出日`。它是**代理判準** —— 用「不等於今天」去反推
「沒有戳上匯出日」。這個推論只在「真實資料日期恰好不是今天」時成立。

**它為什麼必然會誤報**：交易日盤後，`market_index` / `institutional_flow` 的
真實資料日期**本來就是今天**（每日 cron 一提交當日 K 線與三大法人，`MAX(date)`
就是今天）。此時 `as_of == 今天`是**完全正確**的敘述，舊判準卻判它有罪 ——
2026-09-07 `origin/main` CI run #943 即因此轉紅（cron commit `7df6f62` 送進當日資料）。
⚠️ 根本問題不是「太嚴」而是**判不準**：舊判準分不出
「戳上匯出日（真的錯）」與「資料真的就是今天（完全正確）」這兩件事。

**新判準**：`as_of == 該表自己的真實 MAX(date)`（取不到 → NULL）。
這是**因果直驗**，而且射程**嚴格大於**舊判準：
* 舊判準只否決**一個**特定錯值（今天），對其餘所有錯值一律放行 ——
  寫死 `"2020-01-01"`、抄到隔壁表的日期、填 `fetched_at`、差一天、
  把 `MAX` 寫成 `MIN`，舊判準**全部照放**。
* 新判準對**每一列**比對真值，上述每一種都當場轉紅。
* 舊判準唯一能抓、新判準抓不到的情形是「戳上匯出日，而該表真實資料日期
  剛好也是今天」—— 那個情形下 `as_of` 的**值本身是對的**，且已由
  `test_export_never_reads_a_clock_for_as_of` 從「不准去問時鐘」這一側補上。

⚠️ 期望值一律由測試端**獨立重算**（`_ground_truth_as_of`），**不得**呼叫
`E._table_as_of` —— 否則突變會同時污染受測值與期望值，測試退化成 `f(x)==f(x)`
的恆真式，突變測試必然轉綠（§-1.5.E A7：測試要真的守得到東西）。
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


# ── 端到端：as_of 必須等於該表自己的真實資料日期（2026-09-07 由代理判準改為直驗）──
def _ground_truth_as_of(conn: sqlite3.Connection, table: str) -> str | None:
    """測試端**獨立**重算的真值：該表 `MAX(date)` 前 10 碼；取不到 → None。

    「取不到」三種，全部回 None：(a) 表不存在（被 gate 擋 / 缺 token 略過）、
    (b) 表無 `date` 欄（如 `stock_fundamentals`，期別是 roc_year+season）、
    (c) 表為空 / date 全 NULL。

    ⚠️ **刻意不呼叫 `E._table_as_of`**：那會讓突變同時改到受測值與期望值，
    本測試退化成恆真式。此處以獨立 SQL 重算，突變才擋得住（見檔頭）。
    """
    if not conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone():
        return None
    if "date" not in [r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')]:
        return None
    row = conn.execute(f'SELECT MAX("date") FROM "{table}"').fetchone()
    if not row or row[0] is None:
        return None
    return str(row[0])[:10]


def test_export_all_health_as_of_equals_each_table_real_max_date(tmp_path):
    """端到端因果直驗：每列 as_of == 該表自己的真實 `MAX(date)`（取不到 → NULL）。

    取代舊的「as_of != 匯出日」代理判準（2026-09-07，理由與射程對照見檔頭）。
    戳匯出日、寫死日期、抄錯表、填 fetched_at、MAX 寫成 MIN —— 全部當場轉紅。
    """
    db = tmp_path / "stock.db"
    E.export_all(db, token="")
    conn = sqlite3.connect(str(db))
    try:
        rows = list(conn.execute("SELECT field, status, as_of FROM source_health"))
        assert rows, "source_health 必須有列"
        expected = {field: _ground_truth_as_of(conn, field) for field, _s, _a in rows}
    finally:
        conn.close()

    actual = {field: a for field, _s, a in rows}
    bad = {f: (actual[f], expected[f]) for f in actual if actual[f] != expected[f]}
    assert not bad, (
        "下列維度的 as_of 與該表真實資料日期不符 —— as_of 是資料歸屬日，"
        f"不是匯出日、不是任何常數（欄位: (實際, 應為)）：{bad}"
    )

    # 沒寫成功的表不得宣稱任何資料日期（它根本沒有資料）。
    claimed = [f for f, s, a in rows if s == E._HEALTH_ABSENT and a is not None]
    assert not claimed, f"absent 的維度不得帶 as_of：{claimed}"

    # 防空轉：至少要有一張表真的帶得出資料日期，否則上面的比對全是 None == None。
    assert any(v for v in actual.values()), "至少一張表須帶得出真實資料日期"
    assert actual.get("market_index"), "有資料的表必須帶得出真實資料日期"


def test_export_never_reads_a_clock_for_as_of(tmp_path, monkeypatch):
    """`as_of` 不得來自時鐘：把 `_now_tw_date` 換成炸彈，production 路徑碰到就炸。

    這條補上直驗判準唯一的盲區 —— 「戳匯出日，而真實資料日期剛好也是今天」。
    它從**行為**側（不准去問時鐘）而非**數值**側切入，故與「今天是不是交易日」
    完全無關，不會重蹈舊代理判準在盤後必紅的覆轍。
    """
    def _boom() -> str:
        raise AssertionError(
            "production 路徑呼叫了 _now_tw_date()："
            "as_of 是資料歸屬日，不是匯出日（見 export_stock_db._table_as_of）"
        )

    monkeypatch.setattr(E, "_now_tw_date", _boom)
    db = tmp_path / "stock.db"
    E.export_all(db, token="")          # 碰到時鐘 → AssertionError 直接冒出來
    conn = sqlite3.connect(str(db))
    try:
        n = conn.execute("SELECT COUNT(*) FROM source_health").fetchone()[0]
    finally:
        conn.close()
    assert n, "source_health 必須有列（確認上面真的跑完了 export，不是空轉）"
