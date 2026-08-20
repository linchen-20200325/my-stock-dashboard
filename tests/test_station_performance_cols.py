"""持股戰情室 績效欄(張數/均價/現價/損益%/市值)顯示(2026-08 user 需求)。

service build_station_rows 早已算 市值+損益%(#38),但戰情表沒顯示 → user「看不到績效」。
補:service row 加 張數/均價/現價 原值;UI _perf_row 格式化 5 個績效欄(缺→「—」§1)。
"""
from __future__ import annotations

from src.ui.etf.etf_tab_dividend_station import _ETF_COLS, _STOCK_COLS, _perf_row


def test_perf_row_full_data():
    r = {"代號": "0056", "名稱": "高股息", "健檢": "🟢",
         "張數": 13.0, "均價": 11.23, "現價": 12.50, "損益%": 11.3}
    out = _perf_row(r, _ETF_COLS)
    assert out["張數"] == "13"
    assert out["均價"] == "11.23"
    assert out["現價"] == "12.50"
    assert out["損益%"] == "+11.3%"
    # 市值(萬) = 張數 × 現價 × 1000 ÷ 1e4 = 13 × 12.5 ÷ 10 = 16.25 萬
    assert out["市值"] == "16.2萬" or out["市值"] == "16.3萬"  # rounding
    assert out["健檢"] == "🟢"                      # 非績效欄原樣帶過


def test_perf_row_missing_is_dash_not_zero():
    """觀察清單(無金額)/沙箱抓不到現價 → 「—」不捏 0(§1)。"""
    r = {"代號": "6239", "名稱": "力成", "財報體檢": "C（50）",
         "張數": None, "均價": None, "現價": None, "損益%": None}
    out = _perf_row(r, _STOCK_COLS)
    for c in ("張數", "均價", "現價", "損益%", "市值"):
        assert out[c] == "—", f"{c} 應為 —,得 {out[c]}"


def test_perf_row_negative_pnl_signed():
    r = {"張數": 2.0, "均價": 100.0, "現價": 92.0, "損益%": -8.0}
    out = _perf_row(r, _STOCK_COLS)
    assert out["損益%"] == "-8.0%"


def test_cols_include_performance():
    for c in ("張數", "均價", "現價", "損益%", "市值"):
        assert c in _ETF_COLS and c in _STOCK_COLS


def test_service_row_carries_perf_fields():
    """build_station_rows 的 row 應帶 張數/均價/現價 原值(供 UI)。源碼守衛(避免 I/O)。"""
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1]
           / 'src' / 'services' / 'dividend_station_service.py').read_text(encoding='utf-8')
    assert '_row["張數"]' in src and '_row["均價"]' in src and '_row["現價"]' in src
