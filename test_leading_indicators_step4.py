"""
test_leading_indicators_step4.py — leading_indicators.twse_volume Step 4 遷移驗證

驗證重點:
1. 主路徑 FMTQIK 抓到資料時不該觸發備援 (沒回退到 macro_core)。
2. 主路徑全失敗時,備援委派 macro_core.fetch_yf_ohlcv,並能正確
   篩月份 + 套用 [1e8, 1e4, 1e3] 容忍除數。
3. 主路徑 + 備援都失敗時回傳 {}。
4. 結構性: leading_indicators 內不再 import yfinance。
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

import leading_indicators as li


# ══════════════════════════════════════════════════════════════
# 主路徑成功時不應觸發備援
# ══════════════════════════════════════════════════════════════

def test_twse_volume_uses_primary_when_fmtqik_ok(monkeypatch):
    """模擬 FMTQIK 第一個 URL 直接回有效資料,不該打到 macro_core。"""
    captured = {"mc_called": False}

    class _FakeResp:
        def json(self):
            # ROC 日期 113/05/05 = 2024-05-05; 成交金額 (元)
            return {"stat": "OK", "data": [
                ["113/05/05", "1500000", "350000000000", "", "", ""],
                ["113/05/06", "1600000", "380000000000", "", "", ""],
            ]}

    def fake_get(url, params=None, headers=None, timeout=None):
        return _FakeResp()

    import macro_core
    def _fail_mc(*a, **kw):
        captured["mc_called"] = True
        return pd.DataFrame()

    monkeypatch.setattr(li._TWSE_S, "get", fake_get)
    monkeypatch.setattr(macro_core, "fetch_yf_ohlcv", _fail_mc)

    out = li.twse_volume("202405")
    assert "20240505" in out, f"主路徑該回 20240505,實得 {list(out.keys())}"
    assert captured["mc_called"] is False, "主路徑成功時不該觸發 macro_core 備援"


# ══════════════════════════════════════════════════════════════
# 主路徑全失敗 → 備援應委派 macro_core.fetch_yf_ohlcv
# ══════════════════════════════════════════════════════════════

def _build_yf_volume_df(yyyymm: str = "202405", days: int = 5) -> pd.DataFrame:
    """組一個合成的 OHLCV df,Volume 約為 350 億 (raw / 1e8 = 350)。"""
    yr, mo = int(yyyymm[:4]), int(yyyymm[4:6])
    idx = pd.date_range(f"{yr}-{mo:02d}-01", periods=days, freq="B")
    return pd.DataFrame({
        "Open":   [20000] * days,
        "High":   [20100] * days,
        "Low":    [19900] * days,
        "Close":  [20050] * days,
        "Volume": [350 * int(1e8)] * days,
    }, index=idx)


def test_twse_volume_fallback_via_macro_core(monkeypatch):
    captured = {}

    def fake_ohlcv(ticker, range_="9mo", interval="1d"):
        captured["ticker"]   = ticker
        captured["range_"]   = range_
        captured["interval"] = interval
        return _build_yf_volume_df("202405", days=3)

    class _FailResp:
        def json(self):
            return {"stat": "ERR", "data": []}

    monkeypatch.setattr(li._TWSE_S, "get",
                        lambda *a, **kw: _FailResp())
    import macro_core
    monkeypatch.setattr(macro_core, "fetch_yf_ohlcv", fake_ohlcv)

    out = li.twse_volume("202405")

    assert captured["ticker"]   == "^TWII"
    assert captured["range_"]   == "9mo"
    assert captured["interval"] == "1d"
    assert len(out) == 3
    # raw=350e8 / 1e8 = 350.0
    for _v in out.values():
        assert _v == 350.0


def test_twse_volume_fallback_filters_by_month(monkeypatch):
    """備援應只回傳查詢月份的日期,不該夾帶其他月。"""
    yr = 2024
    idx = pd.date_range(f"{yr}-04-25", periods=10, freq="B")  # 跨 4→5 月
    df = pd.DataFrame({
        "Open":   [20000] * 10, "High":  [20100] * 10,
        "Low":    [19900] * 10, "Close": [20050] * 10,
        "Volume": [350 * int(1e8)] * 10,
    }, index=idx)

    class _FailResp:
        def json(self):
            return {"stat": "ERR"}

    monkeypatch.setattr(li._TWSE_S, "get", lambda *a, **kw: _FailResp())
    import macro_core
    monkeypatch.setattr(macro_core, "fetch_yf_ohlcv",
                        lambda *a, **kw: df)

    out = li.twse_volume("202405")
    # 只該保留 2024-05 的日期
    for k in out:
        assert k.startswith("202405"), f"不該夾帶非 5 月: {k}"


def test_twse_volume_returns_empty_on_total_failure(monkeypatch):
    class _FailResp:
        def json(self):
            return {"stat": "ERR"}

    monkeypatch.setattr(li._TWSE_S, "get", lambda *a, **kw: _FailResp())
    import macro_core
    monkeypatch.setattr(macro_core, "fetch_yf_ohlcv",
                        lambda *a, **kw: pd.DataFrame())

    out = li.twse_volume("202405")
    assert out == {}


# ══════════════════════════════════════════════════════════════
# 結構性 — leading_indicators 不該再 import yfinance
# ══════════════════════════════════════════════════════════════

def test_no_yfinance_import_in_leading_indicators():
    src = Path(li.__file__).read_text(encoding="utf-8")
    pattern = re.compile(r"^\s*(?:import|from)\s+yfinance\b", re.MULTILINE)
    matches = pattern.findall(src)
    assert not matches, f"leading_indicators 不應 import yfinance: {matches}"
