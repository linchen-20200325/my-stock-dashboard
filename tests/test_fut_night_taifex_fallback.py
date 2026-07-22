"""test_fut_night_taifex_fallback.py — 致命03 夜盤去 FinMind 單點:TAIFEX futDataDown 官方備援。

覆蓋純轉換(`_parse_taifex_fut_night_csv`)、復用既有 `_fut_night_rows`、以及
`finmind_fut_night` 主/備路由。網路 I/O(`_taifex_fut_daily_csv` POST)只能在真 Actions
run(NAS proxy / 直連 TAIFEX)驗證 — 本 sandbox 封 TW gov;本檔全 offline monkeypatch。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.macro import leading_indicators as LI  # noqa: E402
from src.data.macro.leading_indicators import (  # noqa: E402
    _fut_night_rows,
    _parse_taifex_fut_night_csv,
)

_HDR = ("交易日期,契約,到期月份(週別),開盤價,最高價,最低價,收盤價,"
        "漲跌,漲跌%,成交量,結算價,未沖銷,交易時段")


def _csv(*rows: str) -> str:
    return _HDR + "\n" + "\n".join(rows) + "\n"


@pytest.fixture(autouse=True)
def _clear_cache():
    """清 @_safe_cache,避免 finmind_fut_night 相同 args 命中前一測結果。"""
    try:
        LI.finmind_fut_night.clear()
    except Exception:
        pass
    yield


# ───────────────────────────────────────── 純 parser
def test_parse_maps_sessions_and_filters_tx():
    df = _parse_taifex_fut_night_csv(_csv(
        "2026/07/18,TX,202607,22000,22100,21950,22000,,,100000,,,一般",
        "2026/07/18,TX,202607,22100,22200,22050,22150,,,80000,,,盤後",
        "2026/07/18,MTX,202607,22000,,,22000,,,5000,,,一般",   # 非 TX → 略過
    ))
    assert list(df.columns) == ["date", "trading_session", "close", "volume"]
    assert set(df["trading_session"]) == {"position", "after_market"}   # 一般/盤後
    assert len(df) == 2                                                 # MTX 排除
    assert df[df.trading_session == "after_market"].iloc[0]["close"] == 22150.0


def test_parse_skips_bad_rows():
    df = _parse_taifex_fut_night_csv(_csv(
        "2026/07/18,TX,202607,,,,22000,,,100000,,,一般",     # 有效
        "2026/07/18,TX,202607,,,,0,,,50,,,盤後",              # 收盤=0 → 剔除(§1)
        "bad-date,TX,202607,,,,22000,,,10,,,一般",            # 壞日期 → 剔除
        "2026/07/18,TX,202607,,,,22000,,,10,,,夜盤",          # 未知時段 → 剔除
        "2026/07/18,TX,202607,,,,abc,,,10,,,一般",            # 非數收盤 → 剔除
    ))
    assert len(df) == 1 and df.iloc[0]["date"] == "2026-07-18"


def test_parse_empty_and_missing_columns():
    assert _parse_taifex_fut_night_csv("").empty
    assert _parse_taifex_fut_night_csv("   ").empty
    assert _parse_taifex_fut_night_csv("a,b,c\n1,2,3\n").empty       # 缺必要欄 → 空(§1)


def test_parse_header_whitespace_tolerant():
    csv = (" 交易日期 , 契約 , 交易時段 , 收盤價 , 成交量 \n"
           "2026/07/18,TX,盤後,22150,80000\n"
           "2026/07/18,TX,一般,22000,100000\n")
    assert len(_parse_taifex_fut_night_csv(csv)) == 2                # 欄名容錯(substring)


# ───────────────────────────────────────── 整合既有 _fut_night_rows
def test_parse_feeds_fut_night_rows():
    r = _fut_night_rows(_parse_taifex_fut_night_csv(_csv(
        "2026/07/18,TX,202607,,,,22000,,,100000,,,一般",
        "2026/07/18,TX,202608,,,,21400,,,5,,,一般",            # 遠月量小 → 忽略
        "2026/07/18,TX,202607,,,,22150,,,80000,,,盤後",
    ))).iloc[0]
    assert r["day_close"] == 22000.0 and r["night_close"] == 22150.0  # 各時段挑量大近月
    assert r["chg_pts"] == 150.0


# ───────────────────────────────────────── finmind_fut_night 主/備路由
def _taifex_two_session_csv() -> str:
    return _csv("2026/07/18,TX,202607,,,,22000,,,100000,,,一般",
                "2026/07/18,TX,202607,,,,22150,,,80000,,,盤後")


def test_fallback_when_finmind_empty(monkeypatch):
    monkeypatch.setattr(LI, "finmind_get", lambda *a, **k: pd.DataFrame())   # FinMind 空
    monkeypatch.setattr(LI, "_taifex_fut_daily_csv",
                        lambda *a, **k: _taifex_two_session_csv())
    out = LI.finmind_fut_night("20260601", "20260718", token="x")
    assert not out.empty and out.iloc[0]["night_close"] == 22150.0


def test_no_token_still_uses_taifex(monkeypatch):
    # 去單點:無 FinMind token → 跳過 FinMind、直接走 TAIFEX(免 token 官方源)
    monkeypatch.setattr(LI, "_taifex_fut_daily_csv",
                        lambda *a, **k: _taifex_two_session_csv())
    out = LI.finmind_fut_night("20260601", "20260718", token="")
    assert not out.empty and out.iloc[0]["night_close"] == 22150.0


def test_finmind_wins_taifex_not_called(monkeypatch):
    fm = pd.DataFrame([
        {"date": "2026-07-18", "trading_session": "position", "close": 22000.0, "volume": 100000},
        {"date": "2026-07-18", "trading_session": "after_market", "close": 22150.0, "volume": 80000},
    ])
    monkeypatch.setattr(LI, "finmind_get", lambda *a, **k: fm)

    def _boom(*a, **k):
        raise AssertionError("FinMind 有夜盤資料時不該呼叫 TAIFEX 備援")
    monkeypatch.setattr(LI, "_taifex_fut_daily_csv", _boom)
    out = LI.finmind_fut_night("20260601", "20260718", token="x")
    assert out.iloc[0]["night_close"] == 22150.0
