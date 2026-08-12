"""tests/test_push_weekly_report.py — 週報 cron 的 CSV 代號解析(純函式)。

守衛「發布的 Google Sheet CSV → 台股代號」:有代號欄讀該欄、無則掃 token、
排除數量雜訊、裸碼與 .TW/.TWO 去重。
"""
from __future__ import annotations

from scripts.push_weekly_report import extract_tickers_from_csv


def test_header_ticker_column():
    csv = "name,ticker,updated_at\n台積電,2330,2026-08-01\n聯發科,2454.TW,2026-08-01\n"
    assert extract_tickers_from_csv(csv) == ["2330", "2454"]


def test_header_chinese_daihao():
    csv = "名稱,代號\n台積電,2330\n元大台灣50,0050\n"
    assert extract_tickers_from_csv(csv) == ["2330", "0050"]


def test_ticker_column_ignores_shares_column():
    """有代號欄 → 只讀該欄,數量欄(30000/15000/1000)不誤入。"""
    csv = "ticker,shares\n2330,30000\n2330.TW,15000\n00980D.TWO,1000\n"
    assert extract_tickers_from_csv(csv) == ["2330", "00980D"]   # 2330 去重、00980D 去後綴


def test_no_header_scan_tokens():
    csv = "2330 台積電\n00980A\n2454,聯發科\n"
    assert extract_tickers_from_csv(csv) == ["2330", "00980A", "2454"]


def test_etf_letter_suffix():
    csv = "ticker\n00980A\n00982T\n00980D\n"
    assert extract_tickers_from_csv(csv) == ["00980A", "00982T", "00980D"]


def test_empty_or_garbage():
    assert extract_tickers_from_csv("") == []
    assert extract_tickers_from_csv("你好,世界\nfoo,bar\n") == []


def test_header_variant_contains_match():
    """常見表頭變體(股票代號/證券代碼/stock code)以『包含』命中 → 鎖定該欄,
    數量欄(1101/3000,含真實碼樣式)不誤入(稽核 item 3b 回歸)。"""
    assert extract_tickers_from_csv(
        "股票代號,持股數\n2330,1101\n2454,3000\n") == ["2330", "2454"]
    assert extract_tickers_from_csv(
        "證券代碼,張數\n2330,5\n") == ["2330"]
    assert extract_tickers_from_csv(
        "stock code,shares\n2330,1000\n") == ["2330"]


def test_bom_first_cell():
    """utf-8-sig BOM 在首格 → 去 BOM 後仍正確解析(稽核 item 3e)。"""
    assert extract_tickers_from_csv("\ufeff2330,台積電\n00980A\n") == ["2330", "00980A"]


def test_fullwidth_comma_scan():
    """無表頭、全形逗號分隔 → 正確拆 token(稽核 item 3e)。"""
    assert extract_tickers_from_csv("2330，2454\n") == ["2330", "2454"]
