"""tests/test_push_weekly_report.py — 週報 cron 的 CSV 代號解析(純函式)。

守衛「發布的 Google Sheet CSV → 台股代號」:有代號欄讀該欄、無則掃 token、
排除數量雜訊、裸碼與 .TW/.TWO 去重。
"""
from __future__ import annotations

import pytest

from scripts.push_weekly_report import (
    _fetch_csv,
    _split_urls,
    collect_tickers,
    extract_tickers_from_csv,
)


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


# ── 多來源聯集(組合管理頁 ETF 分頁 + 個股分頁 → 週報自動跟著走)───────────────

def test_split_urls_multiline_dedup():
    """多行/空白分隔 → 去空行、去重、保序;單行=向後相容;空/None → []。"""
    raw = (
        "https://x/pub?gid=0&output=csv\n"
        "  https://x/pub?gid=9&output=csv \n"
        "\n"
        "https://x/pub?gid=0&output=csv\n"   # 與第 1 行重複 → 去重
    )
    assert _split_urls(raw) == [
        "https://x/pub?gid=0&output=csv",
        "https://x/pub?gid=9&output=csv",
    ]
    assert _split_urls("") == [] and _split_urls(None) == []
    assert _split_urls("  https://only/one  ") == ["https://only/one"]


def test_collect_tickers_union_dedup():
    """兩份來源 CSV → 聯集、保序、跨來源去重(ETF∪個股,0050 重疊只留一次)。"""
    _sources = {
        "ETF": "ticker\n00980A\n0050\n",
        "STK": "ticker\n3006\n0050\n",       # 0050 與 ETF 分頁重疊
    }
    out = collect_tickers(["ETF", "STK"], fetch=lambda u: _sources[u])
    assert out == ["00980A", "0050", "3006"]


def test_collect_tickers_fail_loud_on_fetch_error():
    """任一來源抓取失敗 → raise(§1 不送只涵蓋一半的殘缺週報),不吞成半份清單;
    訊息帶「第幾份/共幾份」以利定位,且**不**洩漏 URL。"""
    def _fetch(u: str) -> str:
        if u == "BAD":
            raise RuntimeError("HTTP 404 https://secret/pub?gid=9")   # 例外訊息內嵌 URL
        return "ticker\n2330\n"
    with pytest.raises(RuntimeError, match=r"第 2/2 份") as _ei:
        collect_tickers(["GOOD", "BAD"], fetch=_fetch)
    assert "secret" not in str(_ei.value)      # 外層訊息不得含原始 URL(no-leak)


def test_collect_tickers_empty_tab_not_failure():
    """某分頁抓到但 0 代號(空分頁)不算失敗 → 由聯集後總數決定(此處仍有另一份的碼)。"""
    _sources = {"EMPTY": "ticker\n", "STK": "ticker\n3006\n"}
    assert collect_tickers(["EMPTY", "STK"], fetch=lambda u: _sources[u]) == ["3006"]


def test_fetch_csv_rejects_html_response(monkeypatch):
    """誤用 pubhtml 連結/發布撤銷 → Google 回 text/html(status 200)→ fail loud,
    不讓它靜默解析成 0 代號後被另一分頁掩蓋成殘缺清單(§1)。"""
    class _Resp:
        status_code = 200
        headers = {"content-type": "text/html; charset=UTF-8"}
        apparent_encoding = "utf-8"
        encoding = "utf-8"
        text = "<!DOCTYPE html><html><body>not csv</body></html>"
    monkeypatch.setattr("requests.get", lambda *a, **k: _Resp())
    with pytest.raises(RuntimeError, match=r"非 CSV"):
        _fetch_csv("https://x/pubhtml")


def test_fetch_csv_accepts_csv_response(monkeypatch):
    """正常 text/csv → 照常回傳文字(content-type 守衛不誤殺合法 CSV)。"""
    class _Resp:
        status_code = 200
        headers = {"content-type": "text/csv"}
        apparent_encoding = "utf-8"
        encoding = None
        text = "ticker\n2330\n"
    monkeypatch.setattr("requests.get", lambda *a, **k: _Resp())
    assert _fetch_csv("https://x/pub?output=csv") == "ticker\n2330\n"
