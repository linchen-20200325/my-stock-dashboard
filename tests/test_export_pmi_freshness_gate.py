"""test_export_pmi_freshness_gate.py — 匯出前的台灣 PMI 月頻新鮮度守衛（2026-08-27）。

守的是一個**已實際發生**的錯誤敘述，不是假想情境：
`data_cache/macro_last_good/tw_pmi.json` 是 durable「上次已知良值」，而
`data_cache/metadata.json` 的 `datasets.tw_pmi` 實測
`{last_updated: null, row_count: 0, last_error: "抓取結果為空"}`
→ 即時抓取從未成功、durable 從沒被覆寫，一筆 2026-06 的手動 seed
（`series_id="cier-seed-2026-06"`, value 60.7）天天被 export 成**當期** PMI
推播給下游。§1：錯的數字比沒有數字更危險。

⚠️ 本檔每條都設計成「把 gate revert 掉就轉紅」，不是只驗當下狀態。
"""

from __future__ import annotations

import datetime as dt
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "scripts"))
import export_stock_db as E  # noqa: E402



# ══════════════════════════════════════════════════════════════════════
# 問題 1：PMI 月頻新鮮度 gate
# ══════════════════════════════════════════════════════════════════════
_SEED_2026_06 = {
    "value": 60.7,
    "date": "2026-06-01",
    "label": "中華經濟研究院 PMI（2026-06 官方公布）",
    "source": "CIER 官方公布 2026-06",
    "series_id": "cier-seed-2026-06",
    "cached_at": "2026-07-01T00:00:00",
}


def test_pmi_gate_uses_monthly_ssot_not_local_constant():
    """門檻必須來自既有 SSOT，本檔不得自造發布延遲數字（§3.3 反捏造）。"""
    from shared.staleness import MACRO_PUBLICATION_LAG_DAYS

    assert E._TW_PMI_STALENESS_KEY in MACRO_PUBLICATION_LAG_DAYS, (
        "PMI 的發布延遲必須登錄在 shared/staleness.MACRO_PUBLICATION_LAG_DAYS，"
        "不可在 export 腳本自造第二份門檻"
    )


def test_pmi_gate_blocks_two_month_old_seed():
    """真實事故重現：2026-06 的 seed 在 2026-08-27 匯出 → 必須擋下。"""
    ok, msg = E._tw_pmi_freshness_gate(_SEED_2026_06, today=dt.date(2026, 8, 27))
    assert ok is False, "落後一整個發布期的良值不得外送"
    assert "落後" in msg and "2026-06-01" in msg, f"訊息須點名 as_of 與落後期數：{msg}"


def test_pmi_gate_passes_current_period():
    """當期不得被誤擋 —— 一個 100% 觸發的警告等於沒有警告。"""
    cur = dict(_SEED_2026_06, date="2026-08-01")
    ok, msg = E._tw_pmi_freshness_gate(cur, today=dt.date(2026, 8, 27))
    assert ok is True, f"當期資料不得被擋：{msg}"


def test_pmi_gate_passes_when_upstream_merely_late():
    """上游遲到（原定發布日剛過、仍在緩衝內）→ 放行但要說明，不亮假紅。"""
    ok, msg = E._tw_pmi_freshness_gate(
        dict(_SEED_2026_06, date="2026-06-01"), today=dt.date(2026, 8, 5))
    assert ok is True, f"仍在緩衝內不得擋：{msg}"
    assert "遲到" in msg


@pytest.mark.parametrize("bad", [
    {"value": 60.7},                                   # 缺 date
    {"value": 60.7, "date": ""},                       # date 空
    {"value": 60.7, "date": "not-a-date"},             # date 無法解析
    {"date": "2026-08-01", "value": None},             # 無值
])
def test_pmi_gate_fails_closed_on_unknown_freshness(bad):
    """§1：判不出新鮮度時 fail-closed，不得當成新鮮放行。"""
    ok, _msg = E._tw_pmi_freshness_gate(bad, today=dt.date(2026, 8, 27))
    assert ok is False


def test_pmi_stale_table_is_dropped_not_left_behind(tmp_path):
    """過期時不只是「不寫」，還要把上一輪的舊表 DROP 掉（否則下游讀到更舊的殘表）。"""
    db = tmp_path / "stock.db"
    conn = sqlite3.connect(str(db))
    try:
        pd.DataFrame([{"date": "2026-05-01", "pmi": 59.9, "label": "舊", "source": "舊"}]) \
            .to_sql("macro_tw_pmi", conn, if_exists="replace", index=False)
        n = E.write_macro_tw_pmi(conn)      # 讀 repo 內真實的 seed（2026-06，已過期）
        assert n == -1, "過期良值必須略過整表（回 -1，同 margin/money_supply 慣例）"
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        assert "macro_tw_pmi" not in tables, "過期 → 舊表必須 DROP，不得留殘表給下游"
    finally:
        conn.close()


