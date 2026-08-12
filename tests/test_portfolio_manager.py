"""tests/test_portfolio_manager.py — 📁 投資組合管理頁:純資料轉換 + mount 冒煙。

純函式(rows↔records、codes↔records)測資料正確;AppTest 測未設定 Sheet 時
掛載不炸(顯示提示,不打 gsheet)。CRUD 呼叫的是已測的 gsheet 儲存層,本檔不重測。
"""
from __future__ import annotations

import pytest

from src.ui.tabs.portfolio_manager import (
    codes_to_records,
    etf_rows_to_records,
    records_to_codes,
    records_to_etf_rows,
)


def test_etf_rows_records_roundtrip():
    rows = [{"ticker": "00980A", "lots": 2.0, "avg_price": 15.0}]
    recs = etf_rows_to_records(rows)
    assert recs == [{"代號": "00980A", "張數": 2.0, "均價": 15.0}]
    assert records_to_etf_rows(recs) == [{"ticker": "00980A", "lots": 2.0, "avg_price": 15.0}]


def test_records_to_etf_rows_skips_empty_code():
    recs = [{"代號": "", "張數": 1, "均價": 1}, {"代號": "2330", "張數": 1, "均價": 500}]
    assert records_to_etf_rows(recs) == [{"ticker": "2330", "lots": 1, "avg_price": 500}]


def test_codes_records_dedup_upper():
    assert codes_to_records(["2330", " 00980a ", "", "2330"]) == [
        {"代號": "2330"}, {"代號": "00980a"}, {"代號": "2330"}]
    assert records_to_codes(
        [{"代號": "2330"}, {"代號": " 2330 "}, {"代號": "00980a"}, {"代號": ""}]
    ) == ["2330", "00980A"]            # 大寫 + 去重 + 去空


def test_empty_inputs():
    assert etf_rows_to_records(None) == []
    assert records_to_etf_rows(None) == []
    assert codes_to_records(None) == []
    assert records_to_codes(None) == []


@pytest.mark.slow
def test_manager_mounts_when_unconfigured():
    """未登入 / 未設 Sheet → 顯示提示、不打 gsheet、不炸。"""
    try:
        from streamlit.testing.v1 import AppTest
    except ImportError:
        pytest.skip("streamlit.testing.v1.AppTest 不可用(collection stub 生態)")
    drv = (
        "import sys, os\n"
        "sys.path.insert(0, os.getcwd())\n"
        "from src.ui.tabs.portfolio_manager import render_portfolio_manager\n"
        "render_portfolio_manager()\n"
    )
    at = AppTest.from_string(drv, default_timeout=60).run()
    if at.exception:
        msgs = [f"{e.type}: {str(e.value)[:300]}" for e in at.exception]
        pytest.fail("render_portfolio_manager mount 例外:\n" + "\n".join(msgs))
