"""👤 我的 P1（DEC-083 Q6／Q7）—— L3 `holdings_service.get_holdings` 與 `sector_flow_service` 只讀選定的那一本。

客戶原文 Q7：「🛡️ 持股／🎯 標的／⚡ 行動等頁只能讀這個共同選擇。不得再以『名稱排序第一本』作為不可見的業務決策。」
AI 總管裁示：沒選定 → 不分析（就算只有一本組合也一樣）。
"""
from __future__ import annotations

import ast
import pathlib

import pytest

import src.data.portfolio.oauth_state as ost
from shared import sheet_id as S
from src.data.portfolio import gsheet_portfolio as gsp
from src.services import holdings_service as HS
from src.services import portfolio_binding_service as B
from src.services import sector_flow_service as SF

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_A = "1AbC_dEf-GhIjKlMnOpQrStUvWxYz0123456789abcd"
_B = "2ZyX_wVu-TsRqPoNmLkJiHgFeDcBa9876543210zyxw"
_TOK = {"access_token": "at", "refresh_token": "rt"}

_PORTFOLIOS = {"A長期": [{"ticker": "0056", "lots": 3.0, "avg_price": 30.0}],
               "B波段": [{"ticker": "2330", "lots": 1.0, "avg_price": 500.0}]}
_WATCHLISTS = {"AI 鏈": ["2454", "0056"], "高息": ["00878"]}


class _St:
    def __init__(self, session=None, query=None, secrets=None):
        self.session_state = dict(session or {})
        self.query_params = dict(query or {})
        self.secrets = dict(secrets or {})


@pytest.fixture
def env(monkeypatch):
    """假 `st`（L1 兩支共用）＋ 假 Google（只回本檔的組合 / 觀察清單；記錄每一次讀了哪本、哪個名稱）。"""
    reads: list[tuple] = []

    def _make(session=None, secrets=None, portfolios=_PORTFOLIOS, watchlists=_WATCHLISTS):
        f = _St(session=session, secrets=secrets)
        monkeypatch.setattr(ost, "st", f)
        monkeypatch.setattr(gsp, "st", f)
        monkeypatch.setattr(ost, "sync_silent_marker", lambda: False)
        monkeypatch.setattr(ost, "is_oauth_configured", lambda: True)
        monkeypatch.setattr(gsp, "list_portfolios",
                            lambda **k: reads.append(("list_pf", k["sheet_id"])) or sorted(portfolios))
        monkeypatch.setattr(gsp, "load_portfolio",
                            lambda name, **k: reads.append(("load_pf", k["sheet_id"], name))
                            or list(portfolios[name]))
        monkeypatch.setattr(gsp, "list_stock_watchlists",
                            lambda **k: reads.append(("list_wl", k["sheet_id"])) or sorted(watchlists))
        monkeypatch.setattr(gsp, "load_stock_watchlist",
                            lambda name, **k: reads.append(("load_wl", k["sheet_id"], name))
                            or list(watchlists[name]))
        monkeypatch.setattr("src.services.dividend_station_service.resolve_holding_names", lambda h: h)
        return f
    _make.reads = reads
    return _make


def _bound(sid=_A, **extra):
    return {"gsheet_tokens": dict(_TOK), "portfolio_sheet_id": sid, "stock_portfolio_sheet_id": sid, **extra}


def _select(pf=None, wl=None, skip=False, sid=_A):
    if pf:
        ost.set_active_selection(S.SELECTION_KIND_PORTFOLIO, pf, sid)
    if wl or skip:
        ost.set_active_selection(S.SELECTION_KIND_WATCHLIST, wl or "", sid, skip=skip)


class TestPortfolioSelection:
    def test_not_selected_reads_no_portfolio_even_if_only_one(self, env):
        env(session=_bound(), portfolios={"唯一": [{"ticker": "0050", "lots": 1.0, "avg_price": 1.0}]})
        h = HS.get_holdings()
        assert h.bound and h.held == () and h.portfolio_name == ""
        assert h.portfolio_selection == HS.SELECTION_NOT_SELECTED and h.portfolio_names_n == 1
        assert not any(r[0] == "load_pf" for r in env.reads)

    def test_selected_reads_only_that_one_and_not_the_sorted_first(self, env):
        env(session=_bound())
        _select(pf="B波段")
        h = HS.get_holdings()
        assert h.portfolio_name == "B波段" and h.held_tickers == ("2330",)
        assert ("load_pf", _A, "B波段") in env.reads and ("load_pf", _A, "A長期") not in env.reads
        assert h.portfolio_selection == HS.SELECTION_OK and h.more_portfolios is True

    def test_selected_name_missing(self, env):
        env(session=_bound())
        _select(pf="已改名")
        h = HS.get_holdings()
        assert h.held == () and h.portfolio_selection == HS.SELECTION_MISSING
        assert h.portfolio_selected_missing == "已改名" and not any(r[0] == "load_pf" for r in env.reads)

    def test_empty_sheet_is_not_a_selection_problem(self, env):
        env(session=_bound(), portfolios={})
        h = HS.get_holdings()
        assert h.bound and h.portfolio_selection == "" and h.portfolio_names_n == 0

    def test_selection_from_other_sheet_is_ignored(self, env):
        env(session=_bound())
        _select(pf="B波段", sid=_B)
        h = HS.get_holdings()
        assert h.portfolio_selection == HS.SELECTION_NOT_SELECTED


class TestWatchlistSelection:
    def test_watchlist_reads_same_active_sheet_not_stock_channel(self, env):
        env(session=_bound())
        _select(pf="A長期", wl="AI 鏈")
        h = HS.get_holdings()
        assert {r[1] for r in env.reads} == {_A}
        assert [r for r in h.holdings if not r["held"]] == [
            {**HS._row("2454", held=False)}], "0056 已持有 ⇒ 去重"

    def test_watchlist_not_selected_holdings_still_work(self, env):
        env(session=_bound())
        _select(pf="A長期")
        h = HS.get_holdings()
        assert h.held_tickers == ("0056",) and h.watchlist_name == ""
        assert h.watchlist_selection == HS.SELECTION_NOT_SELECTED
        assert not any(r[0] == "load_wl" for r in env.reads)

    def test_watchlist_skip_reads_nothing(self, env):
        env(session=_bound())
        _select(pf="A長期", skip=True)
        h = HS.get_holdings()
        assert h.watchlist_selection == HS.SELECTION_SKIPPED
        assert not any(r[0] in ("list_wl", "load_wl") for r in env.reads)

    def test_watchlist_missing_name(self, env):
        env(session=_bound())
        _select(pf="A長期", wl="不見了")
        h = HS.get_holdings()
        assert h.watchlist_selection == HS.SELECTION_MISSING and h.watchlist_selected_missing == "不見了"


class TestNotActive:
    @pytest.mark.parametrize("session, secrets, active", [
        (_bound(stock_portfolio_sheet_id=_B), {}, B.ACTIVE_DIVERGED),
        ({"gsheet_tokens": dict(_TOK)}, {"portfolio_sheet_id": _A}, B.ACTIVE_DEPLOY_DEFAULT_ONLY),
        ({"gsheet_tokens": dict(_TOK)}, {}, B.ACTIVE_NONE)])
    def test_no_active_sheet_reads_nothing(self, env, session, secrets, active):
        env(session=session, secrets=secrets)
        h = HS.get_holdings()
        assert not h.bound and h.holdings == () and h.active_state == active
        assert env.reads == []

    def test_logged_out_reads_nothing(self, env):
        env(session={"portfolio_sheet_id": _A, "stock_portfolio_sheet_id": _A})
        h = HS.get_holdings()
        assert not h.bound and env.reads == []


def test_no_sorted_first_subscript_in_holdings_service():
    """AST 守衛：⛔ `_names[0]`／`_wnames[0]`（名稱排序第一本）不得再出現。"""
    tree = ast.parse((_ROOT / "src/services/holdings_service.py").read_text(encoding="utf-8"))
    hits = [ast.unparse(n) for n in ast.walk(tree)
            if isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name)
            and n.value.id in ("_names", "_wnames") and isinstance(n.slice, ast.Constant)]
    assert hits == [], hits


def test_holdings_service_reads_active_selection():
    src = (_ROOT / "src/services/holdings_service.py").read_text(encoding="utf-8")
    assert "get_binding_state(ssot=True)" in src and "get_active_selection(_sid)" in src
    assert "_gsp._get_active_stock_sheet_id()" not in src.split('"""', 2)[2].split("# 👤 我的 P1(DEC-083 Q6")[0]


# ══ sector_flow_service ══════════════════════════════════════════════════════
@pytest.fixture
def cache_ok(monkeypatch):
    monkeypatch.setattr("src.data.sector_flow.reader.read_sector_flow_cache",
                        lambda strict=False: {"ok": True, "sectors": [{"sector": "半導體"}, {"sector": "ETF"}],
                                              "ticker_sector": {"2330": "半導體", "2454": "半導體",
                                                                "0056": "ETF"}})


class TestSectorFlow:
    def test_default_unchanged_ignores_selection(self, env, cache_ok, monkeypatch):
        env(session=_bound())
        called = []
        monkeypatch.setattr(SF, "_active_selection_tickers", lambda: called.append(1) or ([], {}))
        v = SF.get_sector_flow_view(etf_tickers=["0056.TW"], include_stock_watchlists=False)
        assert called == [] and "holding_source" not in v and v["highlight_sectors"] == {"ETF"}

    def test_active_selection_uses_selected_portfolio_and_watchlist(self, env, cache_ok):
        env(session=_bound())
        _select(pf="B波段", wl="高息")
        v = SF.get_sector_flow_view(etf_tickers=["0056.TW"], stock_sheet_id="IGNORED",
                                    use_active_selection=True)
        assert v["highlight_sectors"] == {"半導體"}, "etf_tickers（session 的 ETF 組合列）不得再算進來"
        assert v["holding_source"]["portfolio_name"] == "B波段"
        assert v["holding_source"]["watchlist_name"] == "高息"
        assert not any(r[0] == "list_wl" and r[1] == "IGNORED" for r in env.reads)

    def test_not_selected_highlights_nothing_and_says_so(self, env, cache_ok):
        env(session=_bound())
        v = SF.get_sector_flow_view(use_active_selection=True)
        assert v["highlight_sectors"] == set()
        assert v["holding_source"]["portfolio_selection"] == HS.SELECTION_NOT_SELECTED

    def test_read_error_is_recorded_not_raised(self, env, cache_ok, monkeypatch):
        env(session=_bound())
        _select(pf="B波段")

        def _boom(**_k):
            raise ConnectionError("google down")
        monkeypatch.setattr(gsp, "list_portfolios", _boom)
        v = SF.get_sector_flow_view(use_active_selection=True)
        assert v["ok"] and v["highlight_sectors"] == set()
        assert "google down" in v["holding_source"]["error"]


class TestSectorFlowSourceDetail:
    """PR #927 QA-2 第 3／4 點：holding_source 帶分類代碼與登入狀態，讓 🔍 照實說（⛔ 不露例外原文）。"""

    def test_read_error_is_classified(self, env, cache_ok, monkeypatch):
        env(session=_bound())
        _select(pf="B波段")

        def _boom(**_k):
            raise ConnectionError("google down")
        monkeypatch.setattr(gsp, "list_portfolios", _boom)
        _src = SF.get_sector_flow_view(use_active_selection=True)["holding_source"]
        assert _src["error_issue"] == str(gsp.classify_read_error(ConnectionError("google down")))

    def test_bound_source_carries_login_flags(self, env, cache_ok):
        env(session=_bound())
        _src = SF.get_sector_flow_view(use_active_selection=True)["holding_source"]
        assert _src["logged_in"] is True and _src["login_expired"] is False and _src["error_issue"] == ""
