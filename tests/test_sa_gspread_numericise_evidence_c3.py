"""A-SA-GSPREAD-621-REGRESSION-EVIDENCE-1 — 股票代號前導零 vs 真 gspread numericise 的離線證據。

tests-only、無網路、無憑證、無真 Sheet。用【真 gspread】(`gspread.utils` 純函式 +
真 `gspread.worksheet.Worksheet`,僅把 HTTP client 換成記憶體 fake)核實:

  * 預設 `get_all_records()` 會把 '0050' → int 50(前導零遺失);
  * `numericise_ignore=[欄序(1-based)]` 可保留字串;
  * 現行 `gsheet_sa_reader._worksheet_records` 未傳 ignore ⇒ 現況代號被轉掉零(缺陷現況證據)。

證據分級(請勿混淆):
  FACT      = 本檔對「真 gspread 程式碼」的離線實跑結果(版本見斷言訊息 `gspread.__version__`)。
  INFERENCE = Sheets API 實際回傳格式(儲存格為「純文字」vs「數字格式」時 values.get 回什麼)
              NOT VERIFIED —— 本檔 fake 的 `values_get` 回應是【對 API 回應的敘述】,不是 Google 實測。
修復目標守衛(xfail strict)標明 **C1 HOLD**:修復尚未授權/落地,現況應 xfail;
若某 gspread 版本讓它意外 XPASS,strict 會轉紅 —— 那是要的訊號,不是 bug。
⚠️ 「現況會轉掉零」的測試命名帶 `_current_behavior_evidence`,斷言的是**缺陷現況**,不是期望行為。
"""
from __future__ import annotations

import gspread
import pytest
from gspread.exceptions import GSpreadException
from gspread.http_client import HTTPClient
from gspread.utils import numericise_all, to_records
from gspread.worksheet import Worksheet

import src.data.portfolio.gsheet_sa_reader as R
from src.data.portfolio.gsheet_portfolio import (
    parse_portfolio_records,
    parse_watchlist_records,
)

V = gspread.__version__
TICKERS = ["0050", "00878", "006208", "2330"]


# ── 記憶體 fake(真 Worksheet 的 values_get 路徑) ────────────────────────────
class _FakeHTTPClient(HTTPClient):
    """Worksheet 建構子要求 HTTPClient 實例;不呼叫 super().__init__(不建 session/auth)。"""

    def __init__(self, values):  # noqa: D401 - intentionally skips super().__init__
        self._values = values
        self.calls = []

    def values_get(self, id, range, params=None):  # noqa: A002
        self.calls.append((id, range, params))
        return {"range": range, "majorDimension": "ROWS", "values": self._values}


def _ws(values) -> Worksheet:
    """真 Worksheet + fake client;get_all_records/get_all_values 為真 gspread 程式碼。"""
    client = _FakeHTTPClient(values)
    return Worksheet(spreadsheet=None, properties={"sheetId": 0, "title": "portfolios"},
                     spreadsheet_id="fake-sheet-id", client=client)


def _portfolio_values(tickers=TICKERS):
    rows = [["name", "ticker", "lots", "avg_price", "updated_at"]]
    for t in tickers:
        rows.append(["main", t, "1", "100", "2026-01-01"])
    return rows


class _FakeSpreadsheet:
    def __init__(self, ws):
        self._ws = ws

    def worksheet(self, name):
        return self._ws


class _FakeClient:
    def __init__(self, ws):
        self._sh = _FakeSpreadsheet(ws)

    def open_by_key(self, key):
        return self._sh


# ── 1. 純函式(真 gspread.utils) ─────────────────────────────────────────────
def test_numericise_all_default_strips_leading_zeros_fact():
    out = numericise_all(list(TICKERS))
    assert out == [50, 878, 6208, 2330], f"gspread {V}: {out!r}"
    assert all(isinstance(x, int) for x in out), f"gspread {V}"


def test_numericise_all_ignore_is_one_based_preserves_strings_fact():
    out = numericise_all(list(TICKERS), ignore=[1, 2, 3])
    # 1-based:欄 1~3 保留字串,第 4 欄仍被數字化
    assert out == ["0050", "00878", "006208", 2330], f"gspread {V}: {out!r}"
    # 0-based 誤用(ignore=[0,1,2]):只有 1、2 對到欄 1、2;第 3 欄('006208')仍被轉成 6208
    off = numericise_all(list(TICKERS), ignore=[0, 1, 2])
    assert off == ["0050", "00878", 6208, 2330], f"gspread {V}: {off!r}"


def test_to_records_keys_are_actual_headers_fact():
    rec = to_records(["ticker", "lots"], [["0050", "1"]])
    assert rec == [{"ticker": "0050", "lots": "1"}], f"gspread {V}: {rec!r}"


# ── 2. 真 Worksheet 方法(fake values_get) ───────────────────────────────────
def test_worksheet_get_all_values_returns_raw_strings_fact():
    vals = _ws(_portfolio_values()).get_all_values()
    assert [r[1] for r in vals[1:]] == TICKERS, f"gspread {V}"


def test_worksheet_get_all_records_default_numericises_ticker_fact():
    recs = _ws(_portfolio_values()).get_all_records()
    got = [r["ticker"] for r in recs]
    assert got == [50, 878, 6208, 2330], f"gspread {V}: {got!r}"


def test_worksheet_get_all_records_numericise_ignore_preserves_fact():
    # headers: name(1) ticker(2) lots(3) avg_price(4) updated_at(5) —— ticker 為第 2 欄
    recs = _ws(_portfolio_values()).get_all_records(numericise_ignore=[2])
    got = [r["ticker"] for r in recs]
    assert got == TICKERS, f"gspread {V}: {got!r}"
    # 其他欄仍被數字化(ignore 只作用於指定欄)
    assert recs[0]["lots"] == 1 and recs[0]["avg_price"] == 100, f"gspread {V}"
    allign = _ws(_portfolio_values()).get_all_records(numericise_ignore=["all"])
    assert [r["ticker"] for r in allign] == TICKERS and allign[0]["lots"] == "1", f"gspread {V}"


def test_worksheet_duplicate_header_raises_fact():
    vals = [["name", "ticker", "ticker", "lots"], ["m", "0050", "x", "1"]]
    with pytest.raises(GSpreadException) as ei:
        _ws(vals).get_all_records()
    assert type(ei.value) is GSpreadException, f"gspread {V}: {type(ei.value)!r}"
    assert "duplicates" in str(ei.value), f"gspread {V}: {ei.value}"


def test_worksheet_renamed_or_missing_header_no_error_keys_are_actual_headers_fact():
    # 表頭被改名('代號' 取代 'ticker')、缺 lots/avg_price:get_all_records 不報錯,key 為實際表頭
    vals = [["name", "代號"], ["main", "0050"]]
    recs = _ws(vals).get_all_records(numericise_ignore=["all"])
    assert recs == [{"name": "main", "代號": "0050"}], f"gspread {V}: {recs!r}"
    assert "ticker" not in recs[0]
    # 下游解析器看不到 ticker ⇒ 該列被靜默丟棄(rec.get('ticker','') 為空)
    assert parse_portfolio_records(recs) == []
    assert parse_watchlist_records(recs) == []


# ── 3. 輸入層界限(INFERENCE / NOT VERIFIED) ────────────────────────────────
def test_input_layer_limit_numeric_formatted_cell_cannot_be_restored_inference():
    """INFERENCE / NOT VERIFIED:此處 fake `values_get` 回 '50' 是【我們對「數字格式儲存格的
    顯示字串」的假設敘述】,Sheets API 在 FORMATTED_VALUE 下是否確實回 '50',本檔未連線驗證。
    在該假設成立時:任何 reader(含 numericise_ignore=['all'])都只拿得到 '50',無法還原 '0050'。
    """
    vals = [["name", "ticker", "lots", "avg_price"], ["main", "50", "1", "100"]]
    for kw in ({}, {"numericise_ignore": ["all"]}, {"numericise_ignore": [2]}):
        recs = _ws(vals).get_all_records(**kw)
        assert str(recs[0]["ticker"]) == "50", f"gspread {V} kw={kw}: {recs[0]['ticker']!r}"
        assert str(recs[0]["ticker"]) != "0050"


# ── 4. 現況再現(缺陷現況證據,不是期望行為) ─────────────────────────────────
def test_sa_reader_worksheet_records_current_behavior_evidence():
    """缺陷現況證據,不是期望行為:`_worksheet_records` 呼叫 `ws.get_all_records()` 未帶
    numericise_ignore ⇒ 真 gspread 把 '0050' 等轉成 int,再被 parse_* 轉為 '50'/'878'/'6208'。"""
    client = _FakeClient(_ws(_portfolio_values()))
    recs = R._worksheet_records(client, "sid", "portfolios")
    assert [r["ticker"] for r in recs] == [50, 878, 6208, 2330], f"gspread {V}"
    held = parse_portfolio_records(recs)
    assert [h["ticker"] for h in held] == ["50", "878", "6208", "2330"], f"gspread {V}: {held!r}"


def test_sa_reader_watchlist_current_behavior_evidence():
    """缺陷現況證據,不是期望行為(watchlist 路徑)。"""
    vals = [["name", "ticker", "updated_at"]] + [["w", t, "2026-01-01"] for t in TICKERS]
    client = _FakeClient(_ws(vals))
    recs = R._worksheet_records(client, "sid", "stock_watchlist")
    wl = parse_watchlist_records(recs)
    assert wl == ["50", "878", "6208", "2330"], f"gspread {V}: {wl!r}"


# ── 5. 修復目標守衛(C1 HOLD) ────────────────────────────────────────────────
@pytest.mark.xfail(strict=True, reason=(
    "C1 HOLD:修復(get_all_records(numericise_ignore=[ticker 欄序]) 或改讀 get_all_values)"
    "尚未授權/落地;現況會轉掉前導零。若意外 XPASS(strict 轉紅)= 行為已變,須人工複核。"))
def test_target_sa_reader_preserves_leading_zero_portfolio():
    client = _FakeClient(_ws(_portfolio_values(["0050", "00878", "006208"])))
    held = parse_portfolio_records(R._worksheet_records(client, "sid", "portfolios"))
    assert [h["ticker"] for h in held] == ["0050", "00878", "006208"]


@pytest.mark.xfail(strict=True, reason=(
    "C1 HOLD:修復尚未授權/落地;現況 watchlist 代號會轉掉前導零。"
    "意外 XPASS(strict 轉紅)= 行為已變,須人工複核。"))
def test_target_sa_reader_preserves_leading_zero_watchlist():
    vals = [["name", "ticker", "updated_at"]] + [["w", t, "x"] for t in ["0050", "00878", "006208"]]
    client = _FakeClient(_ws(vals))
    wl = parse_watchlist_records(R._worksheet_records(client, "sid", "stock_watchlist"))
    assert wl == ["0050", "00878", "006208"]
