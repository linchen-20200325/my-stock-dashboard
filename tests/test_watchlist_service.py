"""L3 watchlist_service — 選股網 → 觀察清單 加入編排（#33）。"""
from __future__ import annotations

import pytest

from src.data.portfolio import gsheet_portfolio as gsp
from src.services import watchlist_service as wsvc


def test_add_context_returns_sid_and_names(monkeypatch):
    monkeypatch.setattr(gsp, "_get_active_stock_sheet_id", lambda: "SID")
    monkeypatch.setattr(gsp, "list_stock_watchlists", lambda *, sheet_id=None: ["A", "B"])
    assert wsvc.get_watchlist_add_context() == ("SID", ["A", "B"])


def test_add_context_no_sheet(monkeypatch):
    monkeypatch.setattr(gsp, "_get_active_stock_sheet_id", lambda: "")
    assert wsvc.get_watchlist_add_context() == ("", [])


def test_add_picks_routes_to_l1_with_active_sid(monkeypatch):
    monkeypatch.setattr(gsp, "_get_active_stock_sheet_id", lambda: "SID")
    _seen = {}
    def _add(name, tickers, *, sheet_id=None):
        _seen["call"] = (name, tickers, sheet_id)
        return 3
    monkeypatch.setattr(gsp, "add_to_stock_watchlist", _add)
    assert wsvc.add_picks_to_watchlist("選股池", ["2330", "2454"]) == 3
    assert _seen["call"] == ("選股池", ["2330", "2454"], "SID")   # 用當前個股 sheet


def test_add_picks_no_sheet_raises(monkeypatch):
    monkeypatch.setattr(gsp, "_get_active_stock_sheet_id", lambda: "")
    with pytest.raises(RuntimeError):
        wsvc.add_picks_to_watchlist("A", ["2330"])
