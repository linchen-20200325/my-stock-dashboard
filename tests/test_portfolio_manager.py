"""tests/test_portfolio_manager.py — 📁 投資組合管理頁:純資料轉換 + mount 冒煙。

純函式(rows↔records、codes↔records)測資料正確;AppTest 測未設定 Sheet 時
掛載不炸(顯示提示,不打 gsheet)。CRUD 呼叫的是已測的 gsheet 儲存層,本檔不重測。
"""
from __future__ import annotations

import pytest

from src.ui.tabs.portfolio_manager import (
    codes_to_records,
    etf_rows_to_records,
    parse_sheet_id,
    records_to_codes,
    records_to_etf_rows,
)


def test_parse_sheet_id():
    # 完整編輯 URL → 抓 id
    assert parse_sheet_id(
        "https://docs.google.com/spreadsheets/d/1lFhwvD-ISZ0kf/edit?gid=0#gid=0"
    ) == "1lFhwvD-ISZ0kf"
    # 純 id(含 _ / -)→ 去空白
    assert parse_sheet_id("  1lFhwvD-ISZ0kf  ") == "1lFhwvD-ISZ0kf"
    # 發布連結(pubhtml / pub?output=csv,含 /d/e/<token>)→ 回 ""(非可用 key;管理頁需編輯用
    # URL。舊行為會抓到單字元 "e" → open_by_key("e") 拋錯,屬稽核 A 低度缺失,已修)
    assert parse_sheet_id(
        "https://docs.google.com/spreadsheets/d/e/2PACX-1vQyRldDGV/pubhtml") == ""
    assert parse_sheet_id(
        "https://docs.google.com/spreadsheets/d/e/2PACX-1vQyR/pub?output=csv") == ""
    # 真實 id 以 e 開頭 → **不**誤判為發布連結(只有 /d/e/ 正好單字元 e+斜線才是發布)
    assert parse_sheet_id(
        "https://docs.google.com/spreadsheets/d/eABCdef123/edit") == "eABCdef123"
    assert parse_sheet_id("") == "" and parse_sheet_id(None) == ""


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


@pytest.mark.slow
def test_manager_configured_render_and_load(monkeypatch):
    """已登入 + 設好 Sheet(mock gsheet)→ 兩段 data_editor 都渲染;點 ETF 載入
    走過 load handler(含清 editor delta 的 pop)不炸 —— 涵蓋 CRUD 路徑(DEFECT-1 回歸)。

    ⚠️ gsheet 函式用 `monkeypatch` fixture 打(自動還原);**不可**在 AppTest script 內
    直接改 module attr —— 那會**全域污染** gsheet_portfolio,拖垮後續 test_gsheet_portfolio。
    """
    try:
        from streamlit.testing.v1 import AppTest
    except ImportError:
        pytest.skip("streamlit.testing.v1.AppTest 不可用")
    import src.data.portfolio.gsheet_portfolio as g
    monkeypatch.setattr(g, "_get_active_sheet_id", lambda: "etfsid")
    monkeypatch.setattr(g, "_get_active_stock_sheet_id", lambda: "stksid")
    monkeypatch.setattr(g, "list_portfolios", lambda **k: ["核心配置"])
    monkeypatch.setattr(g, "list_stock_watchlists", lambda **k: ["週報追蹤"])
    monkeypatch.setattr(g, "load_portfolio",
                        lambda n, **k: [{"ticker": "2330", "lots": 1.0, "avg_price": 500.0}])
    monkeypatch.setattr(g, "load_stock_watchlist", lambda n, **k: ["2330", "00980A"])
    drv = (
        "import sys, os\n"
        "sys.path.insert(0, os.getcwd())\n"
        "import streamlit as st\n"
        "st.session_state['gsheet_tokens'] = {'x': 1}\n"
        "from src.ui.tabs.portfolio_manager import render_portfolio_manager\n"
        "render_portfolio_manager()\n"
    )
    at = AppTest.from_string(drv, default_timeout=90).run()
    assert not at.exception, [f"{e.type}: {str(e.value)[:200]}" for e in at.exception]
    # 先選一個既存組合(否則 _pick=='—' 不觸發 load handler)
    _sel = [s for s in at.selectbox if s.key == "_mgmt_etf_pick"]
    assert _sel, "找不到 ETF 載入下拉"
    _sel[0].set_value("核心配置").run()
    # 點 ETF 載入 → load handler(load_portfolio + 清 editor delta 的 pop + rerun)跑過不炸
    _load = [b for b in at.button if b.key == "_mgmt_etf_load"]
    assert _load, "找不到 ETF 載入按鈕"
    _load[0].click().run()
    assert not at.exception, [f"{e.type}: {str(e.value)[:200]}" for e in at.exception]
    # 載入 handler 跑過:名稱回填為所選組合(pop 已在 handler 內清舊 editor delta,
    # 該 key 會隨 editor 重繪再生,故不斷言其缺席,只驗 handler 正常完成 + 回填)。
    assert at.session_state["_mgmt_etf_name"] == "核心配置"
