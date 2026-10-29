"""Visual Fidelity 截圖量測 harness（開發工具，**不是產品程式、不是測試**）。

用途：以 `streamlit run tools/visual_fidelity/harness_app.py` 執行**真的 `app.py`**（含站殼、側欄、
手機底部導覽），但把 L3 service／loader 換成假資料，讓 📊 市場／🎯 標的／💼 持股三頁在沙箱
（沒有外部取數）也能呈現「已載入」狀態，供 `measure_app.js` 截圖與量測。

⛔ 邊界（`docs/governance/UI_VISUAL_FIDELITY_GATE.md` §7）：
- 只供截圖量測；**不得**被 `app.py`、`src/**`、`shared/**` 或 `tests/**` import。
- 檔名刻意不以 `test_` 開頭、也不放在 `tests/`，pytest 不會收集。
- 假資料只活在本 process 的 monkeypatch；不寫 repo、不寫 Sheet、不打外部 API。
- 假資料的數字是**版型量測用的示意值**，不得當成任何投資結論或資料證據引用。

查詢參數：
- `?p=market|target|hold` 選頁（首輪預置導覽頁鍵）。
- `&cold=1` 冷啟動（不預置已載入 session）。
- `&report=1|partial`（📊 市場）預置一份全成功／部分失敗的更新報告。
- `&realflow=1`（🎯 標的）改用 repo 內真本地板塊快取（產業數較多）。
🎯 標的頁的已載入狀態由 `measure_app.js` 依序點「🗺️ 載入板塊地圖 → 🎯 開始選股 → 🔍 查看此檔」。
"""
import datetime as _dt
import pathlib
import runpy
import sys
from types import SimpleNamespace

REPO = str(pathlib.Path(__file__).resolve().parents[2])
if REPO not in sys.path:
    sys.path.insert(0, REPO)

import numpy as np
import pandas as pd
import streamlit as st
from _pytest.monkeypatch import MonkeyPatch

_mp = MonkeyPatch()

# ── 🎯 target: existing UI-T fakes (real dataclasses through real builders) ──
from tests import uit_fakes as U
from src.ui.views import page_find as _F
_REAL_FLOW = _F.__dict__.setdefault('_pcm_real_flow', _F.load_sector_flow)
U.install(_mp, U.Calls())
if st.query_params.get('realflow') == '1' or st.session_state.get('_pcm_realflow'):
    st.session_state['_pcm_realflow'] = True
    _mp.setattr(_F, 'load_sector_flow', _REAL_FLOW)

# ── 📊 market ──
from src.services import market_twii_view_service as S
from src.services import allocation_service as AS
from src.ui.views.risk_cap_gate import SYSTEM_RISK_CAP_NAME

_N = 252
_days = pd.bdate_range(end="2026-10-28", periods=_N)
_rng = np.random.default_rng(7)


def _walk(start, vol):
    return start * np.exp(np.cumsum(_rng.normal(0, vol, _N)))


_tw = _walk(21000, 0.009)
_mp.setattr(S, "get_twii_trend_view", lambda n: S.TwiiTrendView(
    ok=True, xs=tuple(d.strftime("%Y-%m-%d") for d in _days[-n:]), close=tuple(float(x) for x in _tw[-n:]),
    n_available=_N, as_of=_days[-1].strftime("%Y-%m-%d"), is_stale=False))

_ALLOC = SimpleNamespace(
    is_loaded=True, posture="持平", range_text="40%～60%", drivers=("健康分 55",),
    cap_text="🔒 上限 37%", cap_name="", caps=(SimpleNamespace(name=SYSTEM_RISK_CAP_NAME),),
    risk_cap_disclosure=None, conflicts=(), unevaluated_reason="")
_REGIME = {"regime": "bull", "light": "🟢", "source": "warroom", "health": 60, "is_loaded": True,
           "trend_regime": None, "defense": False, "exposure_limit_pct": 37.0, "traffic_light": None}
_mp.setattr(AS, "get_allocation", lambda *a, **k: _ALLOC)
_mp.setattr(AS, "get_macro_regime", lambda *a, **k: dict(_REGIME))
_mp.setattr(AS, "get_breadth_proxy_presence", lambda *a, **k: False)


def _df(arr, n=120):
    return pd.DataFrame({"close": arr[-n:]}, index=_days[-n:])


MARKET_SESSION = {
    "cl_data": {
        "tw": {"台股加權指數": _df(_tw)},
        "intl": {"道瓊工業 DJI": _df(_walk(40000, 0.008)), "納斯達克 IXIC": _df(_walk(17000, 0.011)),
                 "費城半導體 SOX": _df(_walk(5000, 0.016)), "10Y公債殖利率": _df(_walk(4.2, 0.01)),
                 "美元指數 DXY": _df(_walk(100, 0.003))},
        "tech": {}, "inst": {"外資及陸資": {"net": -50.0}}, "margin": 3123.4, "adl": None},
    "macro_info": {"vix": {"current": 21.0, "date": "2026-10-28", "source": "yfinance:^VIX"},
                   "us10y": {"current": 4.3, "date": "2026-10-28"},
                   "ism_pmi": {"value": 48.5, "date": "2026-10-01"},
                   "us_core_cpi": {"yoy": 2.9, "date": "2026-10-01"}},
    "mkt_info": {"index_price": float(_tw[-1]), "index_as_of": "2026-10-28", "ma5": float(_tw[-5:].mean()),
                 "ma60": float(_tw[-60:].mean()), "ma120": float(_tw[-120:].mean()),
                 "ma200": float(_tw[-200:].mean()), "ma200_status": ""},
    "bias_info": {"bias_240": 5.5, "is_estimated": True, "data_days": 252},
    "macro_alerts": [
        {"level": "red", "label": "VIX", "value": 21.0, "unit": "", "message": "波動升溫"},
        {"level": "yellow", "label": "ISM PMI", "value": 48.5, "unit": "", "message": "製造業收縮"},
        {"level": "green", "label": "US10Y", "value": 4.3, "unit": "%", "message": ""}],
}

# ── 💼 hold ──
import src.services.dividend_station_service as DSS
import src.services.holdings_service as HS
import src.services.portfolio_deep_service as PDS
from src.services.dividend_station_service import _PRICE_ASOF_EMPTY

_IDX = pd.date_range("2023-01-06", periods=150, freq="W-FRI")
_HOLD = [
    ("0056", "元大高股息", "etf", 20.0, 32.0), ("00878", "國泰永續高股息", "etf", 30.0, 20.5),
    ("00919", "群益台灣精選高息", "etf", 15.0, 22.0), ("0050", "元大台灣50", "etf", 3.0, 150.0),
    ("006208", "富邦台50", "etf", 5.0, 95.0), ("00713", "元大台灣高息低波", "etf", 8.0, 50.0),
    ("2330", "台積電", "stock", 1.0, 600.0), ("2412", "中華電", "stock", 2.0, 118.0),
]
_ETF_OVER = {"0056": dict(premium_pct=0.3), "00878": dict(premium_pct=1.2, sharpe=0.4),
             "00919": dict(annual_yield_pct=9.0, total_return_1y_pct=-4.0),
             "0050": dict(annual_yield_pct=2.5, total_return_1y_pct=25.0),
             "006208": dict(annual_yield_pct=2.6), "00713": dict(sharpe=-0.2, total_return_1y_pct=-8.0)}


def _etf_metrics(tk):
    _p = dict(_HOLD_PRICE[tk])
    w = pd.Series(np.linspace(_p["lo"], _p["hi"], 150), index=_IDX)
    base = dict(weekly_close=w, premium_pct=0.3, sharpe=0.8, total_return_1y_pct=10.0, annual_yield_pct=5.0,
                inception_years=6.0, ann_return_3y_pct=8.0, cum_return_3y_pct=25.0,
                peer_ranks={3: .2, 6: .2, 12: .2}, current_price=_p["hi"])
    base.update(_ETF_OVER.get(tk, {}))
    return base


_HOLD_PRICE = {"0056": dict(lo=28, hi=37), "00878": dict(lo=17, hi=22.5), "00919": dict(lo=21, hi=23),
               "0050": dict(lo=120, hi=190), "006208": dict(lo=75, hi=110), "00713": dict(lo=48, hi=52)}


def _stock_metrics(tk):
    m = {"mj_grade": "A" if tk == "2330" else "B", "mj_score_pct": 86.0 if tk == "2330" else 64.0,
         "mj_headline": "體質良好" if tk == "2330" else "體質普通", "mj_fail_items": [] if tk == "2330" else ["負債比"],
         "kd_state": None, "current_price": 1010.0 if tk == "2330" else 125.0,
         "name": {**dict((h[0], h[1]) for h in _HOLD), "2454": "聯發科"}[tk], "trend_verdict": {"verdict": "跨季穩定"}}
    m.update(_PRICE_ASOF_EMPTY)
    return m


def _mf(tk, kind):
    return _stock_metrics(tk) if kind == "stock" else _etf_metrics(tk)


_mp.setattr(HS, "get_holdings", lambda **k: HS.HoldingsResult(
    holdings=tuple({"ticker": t, "name": n, "asset_kind": ak, "lots": lots, "avg_price": avg, "held": True}
                   for t, n, ak, lots, avg in _HOLD)
    + ({"ticker": "2454", "name": "聯發科", "asset_kind": "stock", "lots": None, "avg_price": None, "held": False},),
    bound=True, logged_in=True, portfolio_name="主組合", watchlist_name="觀察清單"))
_mp.setattr(DSS, "get_station_rows", lambda hs: (DSS.build_station_rows(hs, vix=21.0, metrics_fn=_mf), 21.0))
_mp.setattr(DSS, "fetch_vix", lambda *a, **k: 21.0)
_mp.setattr(DSS, "get_switch_in_candidates", lambda **k: [
    {"代碼": "2412", "名稱": "中華電", "綜合分": 80}, {"代碼": "2891", "名稱": "中信金", "綜合分": 74}])
_mp.setattr(PDS, "get_portfolio_stress", lambda rows, strict=False: PDS.StressResult(
    computed=True, drop_pct=-20.0, loss_twd=-224000.0, loss_pct=20.4, warn_pct=20.0,
    total_value_twd=1_100_000.0, valued_n=8, held_n=8))
_mp.setattr(PDS, "get_portfolio_var", lambda rows, strict=False: PDS.VarResult(
    computed=True, hist_95_twd=16817.0, hist_99_twd=25000.0, param_95_twd=16000.0, param_99_twd=24000.0,
    monthly_99_twd=95000.0, monthly_99_pct=8.63, warn_pct=10.0, total_value_twd=1_100_000.0, n_common=119,
    n_union=120, first_day="2025-01-02", last_day="2025-06-17", valued_n=8, held_n=8))
_mp.setattr(PDS, "get_dividend_cash_flow", lambda rows, strict=False: PDS.DividendCashResult(
    computed=True, coverage_pct=100.0, gross_twd=30000.0, nhi_twd=0.0, net_after_nhi_twd=30000.0,
    payouts_n=8, tw_n=8, lots_n=8, held_n=8, shares_total=84000.0))

from src.services import trading_calendar_service as _tcs
_mp.setattr(_tcs, "get_today_trading_status", lambda now=None: _tcs.TradingDayStatus(
    today=_dt.date(2026, 10, 29), is_trading_day=True, next_trading_day=_dt.date(2026, 10, 30)))

# ── session presets (first run only) ──
_ss = st.session_state
if "_pcm_init" not in _ss:
    _ss["_pcm_init"] = True
    _p = st.query_params.get("p", "market")
    _ss["_nav4_page"] = {"market": "p4_market", "target": "p4_target", "hold": "p4_hold"}[_p]
    if _p == "market" and st.query_params.get("cold") != "1":
        _ss.update(MARKET_SESSION)
        if st.query_params.get("report") in ("1", "partial"):
            from src.services import macro_refresh_service as RS
            from src.ui.views.page_today import SS_REFRESH_REPORT
            _ss[SS_REFRESH_REPORT] = RS.MacroRefreshReport(
                mode=RS.MODE_WARM, started_at="2026-10-29 13:45", elapsed_s=3.2,
                sources=tuple(RS.SourceResult(k, True, "1.0s") for k in RS.SOURCE_LABELS),
                steps=((RS.StepResult(RS.STEP_CONTENT_AUDIT, False, "5/7 桶完整", partial=True),) if st.query_params.get("report") == "partial" else ()),
                contents=(RS.SourceContent("tw", 1, 1, "檔"), RS.SourceContent("intl", 5, 5, "檔"),
                          RS.SourceContent("inst", 1, 1, "組")),
                written_keys=("cl_data", "macro_info"), popped_keys=(), cleared=())
    if _p == "hold" and st.query_params.get("cold") != "1":
        from src.ui.views import page_hold as PH
        _ss[PH.SS_APPLIED_HOLD] = {"mode": PH.SCOPE_WITH_BINDING}

runpy.run_path(str(pathlib.Path(REPO) / "app.py"), run_name="__main__")
