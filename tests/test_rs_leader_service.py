"""tests/test_rs_leader_service.py — 抗跌 RS 選股 L3 編排測試（v19.70）。

不觸網:monkeypatch 存活池 / 大盤 / 逐檔抓價，用合成 K 線驗編排 + 情境 + 診斷 + AI prompt。
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _series(total_ret: float, n: int = 160, noise: float = 0.012, seed: int = 0) -> pd.DataFrame:
    rng = np.random.RandomState(seed)
    drift = (1 + total_ret) ** (1 / (n - 1)) - 1
    rets = drift + rng.normal(0, noise, n)
    rets[0] = 0.0
    close = 100 * np.cumprod(1 + rets)
    idx = pd.date_range("2026-01-01", periods=n, freq="D")
    return pd.DataFrame({"Close": close}, index=idx)


def _market_series(total_ret=-0.30, n=160, seed=1) -> pd.Series:
    return _series(total_ret, n=n, seed=seed)["Close"]   # fetch_yf_close 回 Series


def _patch_common(monkeypatch, svc, survivors, price_map, market_ret=-0.30):
    monkeypatch.setattr(svc, "_survivor_pool", lambda max_n: list(survivors)[:max_n])
    monkeypatch.setattr(svc, "fetch_yf_close",
                        lambda tk, range_="2y": _market_series(market_ret))
    monkeypatch.setattr(svc, "fetch_stock_history_1y",
                        lambda sid: (price_map.get(sid), f"{sid}.TW"))
    if hasattr(svc._scan_cached, "clear"):
        svc._scan_cached.clear()


def test_scan_ranks_defensive_leaders(monkeypatch):
    import src.services.rs_leader_service as svc
    price_map = {
        "A": _series(+0.10, seed=11),   # 逆勢強
        "B": _series(-0.05, seed=12),   # 小抗跌
        "C": _series(-0.55, seed=13),   # 大輸
    }
    _patch_common(monkeypatch, svc, ["A", "B", "C"], price_map)
    rows, meta = svc.run_rs_leader_scan(lookback=120, name_map={"A": "強者"})
    assert meta["scored"] >= 2
    assert rows[0]["RS(σ)"] >= rows[-1]["RS(σ)"]         # 降冪
    assert rows[0]["名稱"] == "強者"                       # name_map 套用
    assert meta["market"]["is_down"] is True             # 大盤跌情境
    assert "下跌情境" in meta["market"]["banner"]


def test_beat_only_filters(monkeypatch):
    import src.services.rs_leader_service as svc
    price_map = {"A": _series(+0.10, seed=21), "C": _series(-0.55, seed=22)}
    _patch_common(monkeypatch, svc, ["A", "C"], price_map)
    rows, meta = svc.run_rs_leader_scan(lookback=120, beat_only=True)
    assert all(r["贏過大盤"] for r in rows)
    assert "C" not in [r["代碼"] for r in rows]


def test_market_up_banner(monkeypatch):
    import src.services.rs_leader_service as svc
    price_map = {"A": _series(+0.30, seed=31)}
    _patch_common(monkeypatch, svc, ["A"], price_map, market_ret=+0.20)  # 大盤漲
    rows, meta = svc.run_rs_leader_scan(lookback=120)
    assert meta["market"]["is_down"] is False
    assert "語意此時不成立" in meta["market"]["banner"]


def test_market_fetch_fail_failloud(monkeypatch):
    import src.services.rs_leader_service as svc
    monkeypatch.setattr(svc, "_survivor_pool", lambda max_n: ["A"])
    monkeypatch.setattr(svc, "fetch_yf_close", lambda tk, range_="2y": pd.Series(dtype=float))
    if hasattr(svc._scan_cached, "clear"):
        svc._scan_cached.clear()
    rows, meta = svc.run_rs_leader_scan(lookback=60)
    assert rows == []
    assert "^TWII" in meta["note"] and "失敗" in meta["note"]


def test_empty_survivor_pool_failloud(monkeypatch):
    import src.services.rs_leader_service as svc
    monkeypatch.setattr(svc, "_survivor_pool", lambda max_n: [])
    monkeypatch.setattr(svc, "fetch_yf_close", lambda tk, range_="2y": _market_series())
    if hasattr(svc._scan_cached, "clear"):
        svc._scan_cached.clear()
    rows, meta = svc.run_rs_leader_scan(lookback=60)
    assert rows == []
    assert "存活池為空" in meta["note"]


def test_all_insufficient_diagnoses(monkeypatch):
    import src.services.rs_leader_service as svc
    # 個股歷史太短 → 全資料不足
    price_map = {"A": _series(+0.1, n=10, seed=41), "B": _series(-0.1, n=8, seed=42)}
    _patch_common(monkeypatch, svc, ["A", "B"], price_map)
    rows, meta = svc.run_rs_leader_scan(lookback=120)
    assert rows == []
    assert "資料不足" in meta["note"]


def test_price_fetch_none_skips(monkeypatch):
    import src.services.rs_leader_service as svc
    price_map = {"A": _series(+0.10, seed=51), "B": None}   # B 抓不到價
    _patch_common(monkeypatch, svc, ["A", "B"], price_map)
    rows, meta = svc.run_rs_leader_scan(lookback=120)
    assert "A" in [r["代碼"] for r in rows]
    assert "B" not in [r["代碼"] for r in rows]


# ── AI 三型 prompt ────────────────────────────────────────────
def test_build_rs_ai_prompt():
    from src.services.rs_leader_service import build_rs_ai_prompt
    rows = [
        {"代碼": "2330", "名稱": "台積電", "RS(σ)": 1.8, "訊號": "🔴 逆勢強股",
         "個股報酬%": 5.0, "大盤報酬%": -30.0, "超額%": 35.0, "贏過大盤": True},
    ]
    meta = {"lookback": 120, "market": {"banner": "📉 此期間大盤約 -30.0% — 屬下跌情境",
                                        "is_down": True, "market_ret_pct": -30.0}}
    p = build_rs_ai_prompt(rows, meta, top_n=10, news_text="測試新聞")
    assert "抗跌" in p and "2330 台積電" in p
    assert "積極型" in p and "穩健型" in p and "保守型" in p
    assert "下跌情境" in p
    assert "測試新聞" in p


def test_build_rs_ai_prompt_empty():
    from src.services.rs_leader_service import build_rs_ai_prompt
    p = build_rs_ai_prompt([], {"lookback": 60, "market": {}}, top_n=10)
    assert "沒有掃出" in p
