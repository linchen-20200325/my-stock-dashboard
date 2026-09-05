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


# ══════════════════════════════════════════════════════════════════════
# 問題 2：write_macro_tw_pmi 必須真的服從 gate（過期→DROP、當期→寫入）
# ══════════════════════════════════════════════════════════════════════
#
# 【2026-09-05 改寫理由 —— 原版依賴「repo 內的 seed 剛好是過期的」】
# 舊版直接 `E.write_macro_tw_pmi(conn)` 讀 repo 內真實的
# `data_cache/macro_last_good/tw_pmi.json`，註解寫「（2026-06，已過期）」。
# 但那個檔是 cron 每天在覆寫的活檔案（`update_macro_history.yml` cron `0 9 * * *`）：
# 2026-09-04 它已被刷新成 2026-08 的當期值 → 前提消失，gate 正確放行，
# 測試卻仍斷言 `n == -1` 而轉紅。**紅的是測試的前提，不是被守的機制。**
#
# 現在改成自己造 fixture（monkeypatch `E._DATA_CACHE` → tmp_path），驗的是**機制**：
#   - 餵一個確定過期的良值 → 必須回 -1 且把舊表 DROP 掉
#   - 餵一個當期良值       → 必須正常寫入
# 後者是本輪紅燈**恰好證明了是對的**那條行為，就地釘住，
# 免得下次有人為了讓 CI 變綠而把新鮮度閘門本身改壞（把當期也擋掉，
# 那會讓下游永遠少一張表，同樣違背 §1 的初衷）。
#
# 【為什麼這兩條不會隨時間腐爛】
#   - 過期側用**固定的遠古日期**（2019-01-01）：今天過期，十年後只會更過期。
#   - 當期側**不寫死日期**，改用 gate 自己當 oracle 反推「今天算當期的資料月」——
#     時間往前走時它跟著走。⚠️ 這不是循環論證：被驗的命題是
#     「writer 有沒有服從 gate」，date 只是取得一個 gate 認可的輸入。

_STALE_FOREVER = "2019-01-01"   # 遠早於任何未來的 today → 永遠 ≥1 個發布期落後


def _seed(date_str: str) -> dict:
    return dict(_SEED_2026_06, date=date_str)


def _install_seed(monkeypatch, tmp_path, payload: dict) -> None:
    """把 `write_macro_tw_pmi` 讀的良值檔導到 tmp_path，不碰 repo 內的活檔案。"""
    import json as _json

    d = tmp_path / "macro_last_good"
    d.mkdir(parents=True, exist_ok=True)
    (d / "tw_pmi.json").write_text(
        _json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(E, "_DATA_CACHE", tmp_path)


def _current_period_date(today: dt.date | None = None) -> str:
    """反推「今天」被 gate 認定為當期的資料月（YYYY-MM-01）。

    用 `E._tw_pmi_freshness_gate` 自己當 oracle，不在本檔重算一份發布延遲（§3.3）。
    往回找 12 個月仍找不到 → gate 連當期都擋，那本身就是 bug，直接 fail。
    """
    _today = today or dt.date.today()
    y, m = _today.year, _today.month
    for _ in range(12):
        cand = f"{y:04d}-{m:02d}-01"
        ok, _msg = E._tw_pmi_freshness_gate(_seed(cand), today=_today)
        if ok:
            return cand
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    pytest.fail(
        f"回推 12 個月都找不到 gate 認定為當期的資料月（today={_today}）—— "
        "gate 連當期都擋掉了,下游會永遠少一張 macro_tw_pmi 表"
    )


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}


def test_pmi_stale_table_is_dropped_not_left_behind(tmp_path, monkeypatch):
    """過期時不只是「不寫」，還要把上一輪的舊表 DROP 掉（否則下游讀到更舊的殘表）。"""
    _install_seed(monkeypatch, tmp_path, _seed(_STALE_FOREVER))
    conn = sqlite3.connect(str(tmp_path / "stock.db"))
    try:
        pd.DataFrame([{"date": "2026-05-01", "pmi": 59.9, "label": "舊", "source": "舊"}]) \
            .to_sql("macro_tw_pmi", conn, if_exists="replace", index=False)
        assert "macro_tw_pmi" in _tables(conn), "前提:殘表確實先存在"

        n = E.write_macro_tw_pmi(conn)

        assert n == -1, "過期良值必須略過整表（回 -1，同 margin/money_supply 慣例）"
        assert "macro_tw_pmi" not in _tables(conn), \
            "過期 → 舊表必須 DROP，不得留殘表給下游"
    finally:
        conn.close()


def test_pmi_current_period_is_actually_written(tmp_path, monkeypatch):
    """當期良值必須真的寫進去 —— gate 放行了 writer 就不能自己再擋一次。

    對稱於上一條:上一條防「過期卻外送」，這一條防**把閘門修過頭**。
    一個永遠不寫表的 writer 同樣違背 §1（下游只會看到「資料不足」，
    而它其實有當期資料可用）。
    """
    _cur = _current_period_date()
    _install_seed(monkeypatch, tmp_path, _seed(_cur))
    conn = sqlite3.connect(str(tmp_path / "stock.db"))
    try:
        n = E.write_macro_tw_pmi(conn)

        assert n == 1, f"當期良值（date={_cur}）必須寫入 1 列，實得 {n}"
        assert "macro_tw_pmi" in _tables(conn), "當期 → 表必須存在"
        rows = conn.execute("SELECT date, pmi FROM macro_tw_pmi").fetchall()
        assert rows == [(_cur, _SEED_2026_06["value"])], \
            f"寫進去的內容須與良值檔一致，實得 {rows}"
    finally:
        conn.close()
