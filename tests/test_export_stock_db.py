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
    """離線表讀 data_cache 真 parquet；無 token → live 表 Fail-Loud 略過。

    B3 v19.179：`margin` 另受 §3.2 sanity gate 管轄（現況 parquet 為「元 / 張」
    混口徑），故**不**斷言它一定 >0，改斷言「寫了就全列合格 / 沒寫就整表缺席」
    這條與資料狀態無關的不變量（bootstrap 重抓乾淨後自動轉為前者）。
    """
    db = tmp_path / "stock.db"
    res = E.export_all(db, token="")
    for t in ("stock_fundamentals", "market_index", "institutional_flow"):
        assert res[t] > 0, f"{t} 應有列"
    # macro_tw_pmi 2026-08-27 起同受 §2.4 月頻新鮮度 gate 管轄（同 margin / money_supply），
    # 故**不**斷言它一定有列 —— 改在下方斷言與資料狀態無關的不變量。
    # money_supply 2026-08-19 起同受 §3.2 sanity gate 管轄（同 margin），
    # 故**不**斷言它一定有列 —— 改在下方斷言與資料狀態無關的不變量。
    assert res["stock_technical"] == -1        # 缺 token → 略過（不造假）
    assert res["monthly_revenue"] == -1
    assert res["macro_tw_signal"] == -1

    conn = sqlite3.connect(str(db))
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "monthly_revenue" not in tables     # 略過 → 不建空表
    assert "stock_technical" not in tables

    # margin：不變量（不論 parquet 目前乾不乾淨都該成立）
    from shared.margin_schema import margin_twd_sanity_mask
    if res["margin"] < 0:
        assert "margin" not in tables, "sanity 未過 → 整表不得落地（少一張表 ≠ 錯的表）"
    else:
        assert res["margin"] > 0 and "margin" in tables
        vals = pd.read_sql("SELECT margin_balance FROM margin", conn)["margin_balance"]
        assert bool(margin_twd_sanity_mask(vals).all()), \
            "落地的 margin 必須全列通過 §3.2 區間（單位=元）"
    # macro_tw_pmi：不變量（不論 durable 良值目前新不新鮮都該成立）
    #
    # 2026-08-27 加 gate 前，本表是**無條件外送** —— 而 durable 良值檔天生就是
    # 「抓不到時撐著的上次已知值」，實測那筆是 2026-06 的手動 seed
    # （series_id="cier-seed-2026-06"），卻天天被當**當期** PMI 推播給下游。
    from scripts.export_stock_db import _tw_pmi_freshness_gate
    if res["macro_tw_pmi"] < 0:
        assert "macro_tw_pmi" not in tables, \
            "過期 → 整表不得落地（少一張表 ≠ 過期卻標成當期的表）"
    else:
        assert res["macro_tw_pmi"] > 0 and "macro_tw_pmi" in tables
        _pmi = pd.read_sql("SELECT date, pmi FROM macro_tw_pmi", conn)
        _ok, _msg = _tw_pmi_freshness_gate({"date": _pmi["date"].iloc[0],
                                            "value": _pmi["pmi"].iloc[0]})
        assert _ok, f"落地的 macro_tw_pmi 必須通過 §2.4 新鮮度：{_msg}"

    # money_supply：不變量（不論 parquet 目前乾不乾淨都該成立）
    #
    # 2026-08-19 加 gate 前，本表是**無條件外送**——而同檔的 margin 早有 gate，
    # 同一個檔案兩套標準。實測當時 parquet 有 36% 的列貨幣供給額為負，
    # 每日經 `data` 分支送到下游 repo。
    from scripts.export_stock_db import _money_supply_sanity_gate
    if res["money_supply"] < 0:
        assert "money_supply" not in tables, \
            "sanity 未過 → 整表不得落地（少一張表 ≠ 錯的表）"
    else:
        assert res["money_supply"] > 0 and "money_supply" in tables
        _ms = pd.read_sql("SELECT date, m1b, m2, m1b_m2_gap FROM money_supply", conn)
        _ok, _msg = _money_supply_sanity_gate(_ms)
        assert _ok, f"落地的 money_supply 必須全列通過 §3.2：{_msg}"

    cols = [d[1] for d in conn.execute("PRAGMA table_info(stock_fundamentals)")]
    assert {"stock_id", "revenue", "eps", "total_equity"}.issubset(cols)

    # source_health：反映各維成敗（缺 token 的 live 表 → absent；離線表 → ok），不再默默消失
    assert "source_health" in tables
    health = {r[0]: (r[1], r[2]) for r in conn.execute(
        "SELECT field, status, n_rows FROM source_health")}
    assert health["monthly_revenue"][0] == "absent"
    assert health["stock_technical"][0] == "absent"
    assert health["market_index"] == ("ok", res["market_index"])
    # B3：margin 被 sanity gate 擋下時，下游要從 source_health 看得見「這維缺料」
    assert health["margin"][0] == ("absent" if res["margin"] < 0 else "ok")
    # 同精神：money_supply 被擋下時，下游要從 source_health 看得見「這維缺料」，
    # 而不是「這張表從來就不存在」。
    assert health["money_supply"][0] == ("absent" if res["money_supply"] < 0 else "ok")
    # 同精神：PMI 被新鮮度 gate 擋下時，下游要從 source_health 看得見「這維缺料」。
    assert health["macro_tw_pmi"][0] == ("absent" if res["macro_tw_pmi"] < 0 else "ok")
    conn.close()


def test_health_rows_maps_status_and_schema():
    # 2026-08-27：as_of 改吃 {field: 該表自己的資料日期 | None}。
    # 原本是單一匯出日戳記戳滿全表 → 等於宣稱過期資料是今天的（見
    # tests/test_source_health_as_of.py）。
    df = E._health_rows(
        {"market_index": 100, "monthly_revenue": -1, "empty_ok": 0},
        {"market_index": "2026-07-22", "monthly_revenue": None, "empty_ok": None},
    )
    m = {r["field"]: (r["status"], int(r["n_rows"])) for _, r in df.iterrows()}
    assert m["market_index"] == ("ok", 100)
    assert m["monthly_revenue"] == ("absent", 0)     # 缺料 → absent、n_rows 記 0（不造假）
    assert m["empty_ok"] == ("ok", 0)                # 0 列但有寫 → ok
    assert set(df.columns) == set(E._HEALTH_COLS)
    a = {r["field"]: r["as_of"] for _, r in df.iterrows()}
    assert a["market_index"] == "2026-07-22"
    assert a["monthly_revenue"] is None and a["empty_ok"] is None


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
