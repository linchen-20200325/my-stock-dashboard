"""tests/test_rs_leader_ui.py — 抗跌 RS 選股 L5 Streamlit AppTest（v19.70）。

不觸網:在 app script 內把 L3 service 的 fetcher 換成合成資料，實跑 render + 按鈕 →
驗排行表真的畫出來、市場情境橫幅存在。
"""
from __future__ import annotations

from streamlit.testing.v1 import AppTest


def _script():
    import numpy as np
    import pandas as pd

    import src.services.rs_leader_service as svc

    def _series(total_ret, n=160, noise=0.012, seed=0):
        rng = np.random.RandomState(seed)
        drift = (1 + total_ret) ** (1 / (n - 1)) - 1
        rets = drift + rng.normal(0, noise, n)
        rets[0] = 0.0
        close = 100 * np.cumprod(1 + rets)
        return pd.DataFrame({"Close": close},
                            index=pd.date_range("2026-01-01", periods=n, freq="D"))

    price_map = {
        "A": _series(+0.10, seed=11),
        "B": _series(-0.05, seed=12),
        "C": _series(-0.55, seed=13),
    }
    svc._survivor_pool = lambda max_n: ["A", "B", "C"]
    svc.fetch_yf_close = lambda tk, range_="2y": _series(-0.30, seed=1)["Close"]
    svc.fetch_stock_history_1y = lambda sid: (price_map.get(sid), f"{sid}.TW")
    if hasattr(svc._scan_cached, "clear"):
        svc._scan_cached.clear()

    # 名稱對照走網路 → 換成空（避免觸網）
    import src.ui.tabs as _tabs
    _tabs.fetch_twse_yield_pe = lambda: pd.DataFrame()

    from src.ui.tabs.rs_leader_ui import render_rs_leader_screener
    render_rs_leader_screener(gemini_fn=None)


def test_render_and_scan_shows_ranking():
    at = AppTest.from_function(_script).run(timeout=30)
    assert not at.exception
    # 初始:提示點按鈕
    assert any("掃描抗跌強勢股" in b.label for b in at.button)

    # 點掃描
    at.button(key="rs_scan_btn").click().run(timeout=30)
    assert not at.exception

    # 排行表畫出來
    assert len(at.dataframe) >= 1
    df = at.dataframe[0].value
    assert "RS(σ)" in df.columns
    assert "A" in df["代碼"].astype(str).tolist()      # 逆勢強者進榜
    # 市場情境橫幅（大盤跌 → info banner 含「下跌情境」）
    assert any("下跌情境" in str(getattr(b, "value", "")) for b in at.info) or \
           any("下跌情境" in str(getattr(b, "value", "")) for b in at.warning)


def test_render_no_exception_before_scan():
    at = AppTest.from_function(_script).run(timeout=30)
    assert not at.exception
    assert any("抗跌" in m.value for m in at.markdown)
