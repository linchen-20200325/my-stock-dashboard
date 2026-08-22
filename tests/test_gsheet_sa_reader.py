"""L1 守衛 — headless Service-Account 讀持股/觀察清單（每日推播 cron 用,#35）。

涵蓋:純解析器 SSOT（濾值/去重/反捏造）、憑證 fail-loud、read_holdings/read_watchlist
（fake gspread client）、分頁不存在 → 空、跨命名組合去重、空 sheet_id → 空。
"""
from __future__ import annotations

import json

import gspread
import pytest

import src.data.portfolio.gsheet_sa_reader as R
from src.data.portfolio.gsheet_portfolio import (
    parse_portfolio_records,
    parse_watchlist_records,
)


# ── 純解析器 SSOT（§2.1 兩路共用,§1 反捏造）──────────────────────────────
def test_parse_portfolio_filters_dirty_and_zero_rows():
    recs = [
        {"name": "核心", "ticker": "0050", "lots": "2", "avg_price": "130.5"},
        {"name": "核心", "ticker": "2330", "lots": 1, "avg_price": 600},
        {"name": "核心", "ticker": "", "lots": 1, "avg_price": 10},       # 空 ticker
        {"name": "核心", "ticker": "BAD", "lots": 0, "avg_price": 10},    # lots<=0
        {"name": "核心", "ticker": "BAD2", "lots": 1, "avg_price": 0},    # avg<=0
        {"name": "核心", "ticker": "BAD3", "lots": "x", "avg_price": 10}, # 非數
    ]
    out = parse_portfolio_records(recs)
    assert out == [
        {"ticker": "0050", "lots": 2.0, "avg_price": 130.5},
        {"ticker": "2330", "lots": 1.0, "avg_price": 600.0},
    ]


def test_parse_watchlist_dedup_preserve_order_no_price():
    recs = [{"name": "觀察", "ticker": "2317"}, {"name": "觀察", "ticker": "2317"},
            {"name": "觀察", "ticker": "3008"}, {"name": "觀察", "ticker": ""}]
    assert parse_watchlist_records(recs) == ["2317", "3008"]


def test_parsers_empty_input():
    assert parse_portfolio_records([]) == []
    assert parse_watchlist_records(None) == []


# ── 憑證 fail-loud（§1）─────────────────────────────────────────────────
def test_load_sa_credentials_missing_env(monkeypatch):
    monkeypatch.delenv("GCP_SERVICE_ACCOUNT_JSON", raising=False)
    with pytest.raises(ValueError, match="未設定"):
        R.load_sa_credentials()


def test_load_sa_credentials_bad_json(monkeypatch):
    monkeypatch.setenv("GCP_SERVICE_ACCOUNT_JSON", "{not json")
    with pytest.raises(ValueError, match="不是合法 JSON"):
        R.load_sa_credentials()


def test_load_sa_credentials_missing_fields(monkeypatch):
    monkeypatch.setenv("GCP_SERVICE_ACCOUNT_JSON", json.dumps({"client_email": "x@y"}))
    with pytest.raises(ValueError, match="必要欄位"):
        R.load_sa_credentials()


def test_load_sa_credentials_ok(monkeypatch):
    _info = {"client_email": "x@y.iam", "private_key": "---KEY---"}
    monkeypatch.setenv("GCP_SERVICE_ACCOUNT_JSON", json.dumps(_info))
    assert R.load_sa_credentials() == _info


# ── read_holdings / read_watchlist（fake gspread client）──────────────────
class _FakeWS:
    def __init__(self, records):
        self._records = records

    def get_all_records(self):
        return self._records


class _FakeSS:
    def __init__(self, sheets: dict):
        self._sheets = sheets   # {worksheet_name: records}；缺 = WorksheetNotFound

    def worksheet(self, name):
        if name not in self._sheets:
            raise gspread.WorksheetNotFound(name)
        return _FakeWS(self._sheets[name])


class _FakeClient:
    def __init__(self, by_key: dict):
        self._by_key = by_key   # {sheet_id: _FakeSS}

    def open_by_key(self, sid):
        return self._by_key[sid]


def _patch(monkeypatch, by_key):
    monkeypatch.setattr(R, "_build_client", lambda creds: _FakeClient(by_key))


def test_read_holdings_empty_sheet_id_returns_empty():
    assert R.read_holdings("", {}) == []
    assert R.read_watchlist("", {}) == []


def test_read_holdings_parses_and_dedups(monkeypatch):
    _ss = _FakeSS({"portfolios": [
        {"name": "核心", "ticker": "0050", "lots": 2, "avg_price": 130},
        {"name": "衛星", "ticker": "2330", "lots": 1, "avg_price": 600},
        {"name": "另組", "ticker": "0050", "lots": 9, "avg_price": 100},  # 跨組重複 → 去重
    ]})
    _patch(monkeypatch, {"S1": _ss})
    out = R.read_holdings("S1", {"x": 1})
    assert [h["ticker"] for h in out] == ["0050", "2330"]      # 去重保留首見
    assert out[0]["lots"] == 2.0 and out[0]["avg_price"] == 130.0


def test_read_holdings_worksheet_missing_returns_empty(monkeypatch):
    _patch(monkeypatch, {"S1": _FakeSS({})})   # 無 portfolios 分頁
    assert R.read_holdings("S1", {}) == []


def test_read_watchlist_parses(monkeypatch):
    _ss = _FakeSS({"stock_watchlist": [
        {"name": "觀察", "ticker": "2317"}, {"name": "觀察", "ticker": "3008"}]})
    _patch(monkeypatch, {"S1": _ss})
    assert R.read_watchlist("S1", {}) == ["2317", "3008"]


def test_read_watchlist_worksheet_missing_returns_empty(monkeypatch):
    _patch(monkeypatch, {"S1": _FakeSS({})})
    assert R.read_watchlist("S1", {}) == []


def test_scopes_are_readonly():
    """§1 最小權限:cron 只讀不寫使用者 Sheet。"""
    assert R._SCOPES == ["https://www.googleapis.com/auth/spreadsheets.readonly"]
