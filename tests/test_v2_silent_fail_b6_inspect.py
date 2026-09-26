"""批次 6：「🔬 查一檔」—— 抓取失敗 ≠ 真的沒有（客戶 2026-09-26：本批放行「失敗被當成沒結果」的所有卡）。

修了哪幾張卡（每張都走該卡**既有**的紅態 `*_FAILED_NOW`；why 一律 `_error_why(SRC_*, …)`，
L3 **回報**失敗（沒有例外可找）時動詞用「回報失敗」—— 同籌碼卡的判例；⛔ 不新造文案）：

  · `inspect.stock.health`     財報三張表任一沒拿到 FinMind 成功回應（例外／非 200）、或體檢拋例外
                               ← L1 `fetch_financial_statements(failed=)` → L3 `fetch_metrics(failed=)`
  · `inspect.stock.valuation`  現價那一腿抓取失敗（L1 `get_combined_data(strict=True)` 的暫時性失敗）
                               或個股那一輪 L3 拋例外 —— 原本 L2 回「無股價，…不適用」灰卡
  · `inspect.profit.*`         損益表那一腿（或整份財報）抓取失敗 —— 原本錯誤 dict 寫「無此股票財報資料」
  · `inspect.etf.dividend`     L1 `fetch_etf_dividends` 的 `attrs['fetch_failed']`（PR #694）
  · `inspect.etf.premium`      L3 那一層的例外（`calc_premium_discount` 自己吞掉的例外本層分不開，照舊）
  · `inspect.etf.peer`         同儕 ≥ `PEER_MIN_GROUP_SIZE` 檔卻回頂層 `_err`（批次價格抓空／例外）或例外

沒修（分不開，照舊灰）：`inspect.stock.chips` 的灰態（三大法人四源各自吞錯、回原 df）、
估值的配息備援鏈（yfinance 段在 L1 `cached_dividends` 就吞成空序列、TWSE 非 OK 回應同時用於「沒有」與錯誤）。

每條失敗路徑三件事（同批次 1～4）：
  (a) 上游失敗 → 紅卡；部分失敗也紅（⛔ 不得是 live 的半份結論、⛔ 不得是灰卡「有效的結果」）；
  (b) 真的沒有 → 與改前一個 byte 都不差；其他卡、其他頁（葉2 批次、💼 我的持股）不變；
  (c) 突變：拿掉本批任一條新判定 → (a) 必須失敗。
"""
from __future__ import annotations

import hashlib
import importlib.util
import pathlib
import sys
import types

import pandas as pd
import pytest
import requests

import src.data.core.financial_statements_fetcher as FFS
import src.services.dividend_station_service as DS
from shared import dividend_station_thresholds as T
from shared.ui_state import UI_EMPTY, UI_FAILED, UI_LIVE
from src.ui.views import page_inspect as P

_REPORTED = "回報失敗"
_RAISED = "拋出例外"
_VALID = "有效的結果"
_IS = FFS.DATASET_INCOME_STATEMENT
_BS, _CF = "TaiwanStockBalanceSheet", "TaiwanStockCashFlowsStatement"


def _mutant(mod: types.ModuleType, *pairs: tuple[str, str]) -> types.ModuleType:
    """把 `mod` 的原始碼裡每一組 `old` **恰好一處**換成 `new`，載成一個獨立的新模組。"""
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    for old, new in pairs:
        assert src.count(old) == 1, f"突變點不唯一或已不存在：{old!r}"
        src = src.replace(old, new)
    name = f"_mutant_b6_{mod.__name__.rsplit('.', 1)[-1]}"
    spec = importlib.util.spec_from_loader(name, loader=None)
    m = importlib.util.module_from_spec(spec)
    m.__file__ = mod.__file__
    sys.modules[name] = m
    try:
        exec(compile(src, mod.__file__, "exec"), m.__dict__)
    finally:
        sys.modules.pop(name, None)
    return m


def _html(built) -> str:
    card, facts, sig = built
    return P.v2_card_html(card, facts, sig)


# ══════════════════════════════════════════════════════════════════
# 離線 L1：FinMind 三個 dataset 的回應由測試指定（不打網路、不碰 yfinance）
# ══════════════════════════════════════════════════════════════════
_D = "2026-06-30"
_BS_ROWS = [{"date": _D, "type": t, "value": v} for t, v in (
    ("TotalAssets", 1000), ("TotalLiabilities", 400), ("CashAndCashEquivalents", 200),
    ("AccountsReceivable", 80), ("Equity", 600), ("CurrentAssets", 500),
    ("CurrentLiabilities", 200))]
_CF_ROWS = [{"date": _D, "type": "CashFlowsFromOperatingActivities", "value": 50}]
_IS_ROWS = [{"date": _D, "type": t, "value": v} for t, v in (
    ("Revenue", 500), ("GrossProfit", 200), ("OperatingIncome", 100),
    ("IncomeAfterTaxes", 80))]


def _ok(rows):
    return {"status": 200, "data": rows}


_QUOTA = {"status": 402, "msg": "Requests reach the upper limit"}
_DOWN = ConnectionError("proxy down")

#: 情境 → 三個 dataset 的回應。
_ALL_OK = {_BS: _ok(_BS_ROWS), _CF: _ok(_CF_ROWS), _IS: _ok(_IS_ROWS)}
_NONE = {_BS: _ok([]), _CF: _ok([]), _IS: _ok([])}                    # 真的沒有財報
_ALL_DOWN = {_BS: _DOWN, _CF: _DOWN, _IS: _DOWN}                        # 全部連不上
_QUOTA_ALL = {_BS: _QUOTA, _CF: _QUOTA, _IS: _QUOTA}                    # 額度用罄
_IS_FAIL = {_BS: _ok(_BS_ROWS), _CF: _ok(_CF_ROWS), _IS: _QUOTA}        # 部分：損益表沒拿到
_CF_FAIL = {_BS: _ok(_BS_ROWS), _CF: _DOWN, _IS: _ok(_IS_ROWS)}         # 部分：現金流沒拿到
_IS_NONE = {_BS: _ok(_BS_ROWS), _CF: _ok(_CF_ROWS), _IS: _ok([])}       # 真的沒有損益表


class _Resp:
    def __init__(self, j):
        self._j = j

    def json(self):
        return self._j


@pytest.fixture
def finmind(monkeypatch):
    """回一個 setter：`finmind(plan)` 之後，財報 L1 就照 plan 回應。快取每次清空。"""
    import yfinance

    def _no_yf(*_a, **_k):
        raise AssertionError("測試資料不該觸發 yfinance 備援（會打網路）")

    monkeypatch.setattr(yfinance, "Ticker", _no_yf)
    plan: dict = {}

    def _get(url, params=None, headers=None, timeout=None):
        v = plan[params["dataset"]]
        if isinstance(v, Exception):
            raise v
        return _Resp(v)

    monkeypatch.setattr(requests, "get", _get)

    def _set(p):
        plan.clear()
        plan.update(p)
        FFS._fetch_financial_statements_cached.clear()

    yield _set
    FFS._fetch_financial_statements_cached.clear()


@pytest.fixture
def stock_env(monkeypatch, finmind):
    """個股 L3 的其餘外部依賴離線化：名稱、token、日線（由 `price=` 指定三種行為）。"""
    import src.config.config as C
    import src.config.stock_names as N
    import src.data.core.data_loader as DL

    monkeypatch.setattr(C, "get_finmind_token", lambda: "tok")
    monkeypatch.setattr(N, "get_stock_name", lambda code: "測試股")
    monkeypatch.setattr(DL.StockDataLoader, "__init__", lambda self, *a, **k: None)
    _idx = pd.bdate_range("2025-01-02", periods=120)
    _px = pd.Series([100.0 + (i % 5) for i in range(len(_idx))], index=_idx)
    _df = pd.DataFrame({"close": _px, "high": _px + 1, "low": _px - 1})

    def _set(fin_plan, price="ok"):
        finmind(fin_plan)

        def _cached(self, sid, days, use_adjusted=True):
            if price == "ok":
                return _df, None, "測試股"
            if price == "none":                     # L1 的確定性負結果（照舊快取、不拋）
                return None, "❌ 查無資料", None
            raise DL._CombinedDataError("系統錯誤: ReadTimeout")   # 暫時性失敗
        monkeypatch.setattr(DL.StockDataLoader, "_get_combined_data_cached", _cached)
    return _set


def _stock_verdict():
    return P.KindVerdict(requested=True, code="2330", auto_kind="stock", kind="stock",
                         kind_label="個股", auto_kind_label="個股", is_stock=True,
                         benchmark="0050")


def _etf_verdict():
    return P.KindVerdict(requested=True, code="00878", auto_kind="etf", kind="etf",
                         kind_label="ETF", auto_kind_label="ETF", is_etf=True)


# ══════════════════════════════════════════════════════════════════
# 離線 ETF L1／L2
# ══════════════════════════════════════════════════════════════════
_DIV_ATTR = __import__("src.data.etf.etf_fetch", fromlist=["x"]).DIVIDENDS_FETCH_FAILED_ATTR


def _divs(kind: str) -> pd.Series:
    if kind == "ok":
        return pd.Series([0.5, 0.5], index=pd.to_datetime(
            [pd.Timestamp.today() - pd.Timedelta(days=100),
             pd.Timestamp.today() - pd.Timedelta(days=10)]))
    s = pd.Series(dtype=float)
    if kind == "failed":
        s.attrs[_DIV_ATTR] = "ConnectionError: Yahoo 429"
    return s                                           # "none" → 真的沒配息（無旗標）


@pytest.fixture
def etf_env(monkeypatch):
    """回一個 setter：`etf_env(div=, premium=, peer=)` —— ETF 三腿各自的行為。"""
    import src.compute.etf.etf_calc as EC
    idx = pd.bdate_range("2020-01-02", periods=900)
    px = pd.DataFrame({"Close": [30.0 + (i % 7) * 0.3 for i in range(len(idx))]}, index=idx)

    def _set(div="ok", premium="ok", peer="ok"):
        fake = types.ModuleType("src.data.etf.etf_fetch")
        fake.DIVIDENDS_FETCH_FAILED_ATTR = _DIV_ATTR
        fake.fetch_etf_price = lambda t, period="5y": px
        fake.fetch_etf_dividends = lambda t: _divs(div)
        fake.fetch_etf_info = lambda t, *a, **k: {}
        monkeypatch.setitem(sys.modules, "src.data.etf.etf_fetch", fake)

        def _prem(info, df, tk=""):
            if premium == "raise":
                raise TimeoutError("iNAV relay timeout")
            return {"premium_pct": 0.4 if premium == "ok" else None}
        monkeypatch.setattr(EC, "calc_premium_discount", _prem)

        def _peer(t, periods=(63, 126, 252)):
            if peer == "raise":
                raise RuntimeError("peer boom")
            if peer == "few":        # 同儕不足（真的沒有）
                return {"_err": "同儕資料不足", "category": "x", "peers": ["a"]}
            if peer == "nofetch":    # 同儕夠，但批次價格抓空（L2 自己的話）
                return {"_err": "yfinance 抓不到價格", "category": "x",
                        "peers": ["a", "b", "c"]}
            return {63: {"percentile": 80.0}, 126: {"percentile": 70.0},
                    252: {"percentile": 60.0}, "category": "x", "peers": ["a", "b", "c"]}
        monkeypatch.setattr(EC, "compute_etf_peer_ranking", _peer)
        monkeypatch.setattr("src.compute.etf.etf_quality.compute_etf_quality",
                            lambda t: {"stars": None}, raising=False)
        monkeypatch.setattr("src.services.etf_scoring_service.ensure_etf_rf_injected",
                            lambda: None, raising=False)
    return _set


# ══════════════════════════════════════════════════════════════════
# (a)(b) L1：`fetch_financial_statements(failed=)`
# ══════════════════════════════════════════════════════════════════
class TestL1StatementsMarker:
    @pytest.mark.parametrize("plan,want", [
        (_ALL_DOWN, {_BS, _CF, _IS}), (_QUOTA_ALL, {_BS, _CF, _IS}),
        (_IS_FAIL, {_IS}), (_CF_FAIL, {_CF})], ids=["down", "quota", "is", "cf"])
    def test_a_failed_datasets_are_reported(self, finmind, plan, want):
        finmind(plan)
        f: dict = {}
        FFS.fetch_financial_statements("9901", "tok", failed=f)
        assert set(f) == want and all(f.values())

    @pytest.mark.parametrize("plan", [_ALL_OK, _NONE, _IS_NONE], ids=["ok", "none", "is-none"])
    def test_b_status_200_is_never_a_failure(self, finmind, plan):
        finmind(plan)
        f: dict = {}
        FFS.fetch_financial_statements("9902", "tok", failed=f)
        assert f == {}, "200（含 200 但沒有資料）＝ 真的沒有，不是抓取失敗"

    @pytest.mark.parametrize("plan", [_ALL_OK, _NONE, _ALL_DOWN, _IS_FAIL, _CF_FAIL])
    def test_b_default_callers_get_the_same_dict_without_any_marker(self, finmind, plan):
        """不傳 `failed=` 的既有呼叫端：回傳值 ＝ 快取本體拿掉私有鍵（其餘逐鍵相同）。"""
        finmind(plan)
        _cached = FFS._fetch_financial_statements_cached("9903", "tok")
        out = FFS.fetch_financial_statements("9903", "tok")
        assert FFS._FETCH_FAILED_KEY not in out
        want = {k: v for k, v in _cached.items() if k != FFS._FETCH_FAILED_KEY}
        assert set(out) == set(want)
        assert {k: v for k, v in out.items() if k != "fetched_at"} == {
            k: v for k, v in want.items() if k != "fetched_at"}
        if plan in (_ALL_OK, _NONE):
            assert FFS._FETCH_FAILED_KEY not in _cached, "沒有失敗時快取本體也不帶旗標"

    def test_b_error_dict_text_is_unchanged(self, finmind):
        finmind(_ALL_DOWN)
        assert FFS.fetch_financial_statements("9904", "tok") == {
            "error": "9904：FinMind 無此股票財報資料（可能為新掛牌、未上市、或 FinMind 資料源尚未收錄）"}

    def test_marker_survives_a_cache_hit(self, finmind):
        finmind(_QUOTA_ALL)
        FFS.fetch_financial_statements("9905", "tok")          # 填快取
        f: dict = {}
        FFS.fetch_financial_statements("9905", "tok", failed=f)
        assert set(f) == {_BS, _CF, _IS}, "第二次（命中快取）不得看起來就成功了"


# ══════════════════════════════════════════════════════════════════
# (a)(b) L3：`fetch_metrics(failed=)`
# ══════════════════════════════════════════════════════════════════
class TestL3Reports:
    def test_a_statements_failure_is_reported(self, stock_env):
        stock_env(_QUOTA_ALL)
        f: dict = {}
        DS.fetch_metrics("2330", T.KIND_STOCK, failed=f)
        assert "402" in f[DS.FAILED_STATEMENTS] and DS.FAILED_PRICE not in f

    def test_a_partial_statements_failure_is_reported_even_if_a_score_exists(self, stock_env):
        stock_env(_CF_FAIL)
        f: dict = {}
        m = DS.fetch_metrics("2330", T.KIND_STOCK, failed=f)
        assert m["mj_score_pct"] is not None, "前提：少一張表時 L3 仍會算出一個分數"
        assert _CF in f[DS.FAILED_STATEMENTS]

    def test_a_statements_exception_is_reported(self, stock_env, monkeypatch):
        stock_env(_ALL_OK)
        import src.services.financial_health_engine as FHE

        def _boom(*a, **k):
            raise KeyError("x")
        monkeypatch.setattr(FHE, "analyze_financial_health", _boom)
        f: dict = {}
        DS.fetch_metrics("2330", T.KIND_STOCK, failed=f)
        assert f[DS.FAILED_STATEMENTS].startswith("KeyError")

    def test_a_transient_price_failure_is_reported(self, stock_env):
        stock_env(_ALL_OK, price="raise")
        f: dict = {}
        m = DS.fetch_metrics("2330", T.KIND_STOCK, failed=f)
        assert m["current_price"] is None and "ReadTimeout" in f[DS.FAILED_PRICE]

    @pytest.mark.parametrize("plan,price", [(_NONE, "ok"), (_ALL_OK, "none"), (_ALL_OK, "ok")],
                             ids=["no-statements", "no-price", "all-ok"])
    def test_b_genuine_none_is_not_reported(self, stock_env, plan, price):
        stock_env(plan, price=price)
        f: dict = {}
        DS.fetch_metrics("2330", T.KIND_STOCK, failed=f)
        assert f == {}

    @pytest.mark.parametrize("plan,price", [
        (_ALL_OK, "ok"), (_NONE, "ok"), (_QUOTA_ALL, "raise"), (_CF_FAIL, "none")])
    def test_b_failed_mode_does_not_change_the_returned_metrics(self, stock_env, plan, price):
        """其他呼叫端（💼 我的持股 / 推播腳本）不傳 `failed=`：回傳值與傳了之後一模一樣。"""
        stock_env(plan, price=price)
        a = DS.fetch_metrics("2330", T.KIND_STOCK)
        stock_env(plan, price=price)
        b = DS.fetch_metrics("2330", T.KIND_STOCK, failed={})
        assert a == b

    def test_b_default_mode_still_swallows_the_transient_price_failure(self, stock_env):
        """既有行為：不傳 `failed=` → 不走 strict，暫時性失敗照舊還原成 (None, err, None)。"""
        stock_env(_ALL_OK, price="raise")
        m = DS.fetch_metrics("2330", T.KIND_STOCK)
        assert m["current_price"] is None and m["mj_score_pct"] is not None

    @pytest.mark.parametrize("leg,kw,key", [
        ("dividend", {"div": "failed"}, DS.FAILED_DIVIDEND),
        ("premium", {"premium": "raise"}, DS.FAILED_PREMIUM),
        ("peer-nofetch", {"peer": "nofetch"}, DS.FAILED_PEER),
        ("peer-raise", {"peer": "raise"}, DS.FAILED_PEER)])
    def test_a_etf_leg_failures_are_reported(self, etf_env, leg, kw, key):
        etf_env(**kw)
        f: dict = {}
        DS.fetch_metrics("00878", T.KIND_ETF, failed=f)
        assert set(f) == {key}

    @pytest.mark.parametrize("kw", [{"div": "none"}, {"premium": "none"}, {"peer": "few"}, {}],
                             ids=["no-div", "no-inav", "few-peers", "all-ok"])
    def test_b_etf_genuine_none_is_not_reported(self, etf_env, kw):
        etf_env(**kw)
        f: dict = {}
        DS.fetch_metrics("00878", T.KIND_ETF, failed=f)
        assert f == {}

    @pytest.mark.parametrize("kw", [{"div": "failed"}, {"premium": "raise"}, {"peer": "nofetch"},
                                    {"peer": "raise"}, {}])
    def test_b_etf_failed_mode_does_not_change_the_returned_metrics(self, etf_env, kw):
        etf_env(**kw)
        a = DS.fetch_metrics("00878", T.KIND_ETF)
        b = DS.fetch_metrics("00878", T.KIND_ETF, failed={})
        assert a.keys() == b.keys()
        for k in a:
            if isinstance(a[k], pd.Series):
                assert a[k].equals(b[k])
            else:
                assert a[k] == b[k], k


# ══════════════════════════════════════════════════════════════════
# (a) 查一檔：抓取失敗 → 該卡既有的紅態
# ══════════════════════════════════════════════════════════════════
def _assert_red(card, now, *, source=P.SRC_METRICS, verb=_REPORTED):
    assert card.state == UI_FAILED, (card.key, card.state)
    assert card.note.now == now
    assert card.note.why.startswith(P.scrub_state_glyphs(source)[0] + verb + "："), card.note.why
    assert _VALID not in card.note.why


def _health(P_=P):
    return P_.build_health_card(P_.load_stock_readout(_stock_verdict()))


def _valuation(P_=P):
    _v = _stock_verdict()
    return P_.build_valuation_card(P_.load_valuation(_v, P_.load_stock_readout(_v)))


def _profit(P_=P):
    return P_.build_profit_cards(P_.load_profitability(_stock_verdict()))


def _etf(P_=P):
    e = P_.load_etf_readout(_etf_verdict())
    return P_.build_premium_card(e), P_.build_dividend_card(e), P_.build_peer_card(e)


class TestHealthCard:
    @pytest.mark.parametrize("plan", [_ALL_DOWN, _QUOTA_ALL, _IS_FAIL],
                             ids=["down", "quota", "is"])
    def test_a_statement_fetch_failure_is_red(self, stock_env, plan):
        stock_env(plan)
        card, facts, sig = _health()
        _assert_red(card, P.HEALTH_FAILED_NOW)
        assert sig == ""

    def test_a_partial_failure_with_a_score_is_red_not_live(self, stock_env):
        """少一張現金流量表：L3 仍算出一個「少評了幾項」的分數 → ⛔ 不得 live，也不得把分數放上紅卡。"""
        stock_env(_CF_FAIL)
        card, facts, _ = _health()
        _assert_red(card, P.HEALTH_FAILED_NOW)
        assert {k for k, _ in facts} <= {"名稱", "現價"}, facts

    def test_b_genuinely_no_statements_stays_grey(self, stock_env):
        stock_env(_NONE)
        card, _, _ = _health()
        assert card.state == UI_EMPTY and card.note.now == P.HEALTH_EMPTY_NOW


class TestValuationCard:
    def test_a_transient_price_failure_is_red_not_not_applicable(self, stock_env, monkeypatch):
        stock_env(_ALL_OK, price="raise")
        import src.services.valuation_service as VS

        def _no(*_a, **_k):
            raise AssertionError("缺一半輸入就算不出位階，配息那一腿不必再抓")
        monkeypatch.setattr(VS, "get_stock_dividends", _no)
        card, _, _ = _valuation()
        _assert_red(card, P.VALUATION_FAILED_NOW)
        assert "無股價" not in card.note.why

    def test_a_whole_stock_fetch_exception_is_red(self):
        v = P.load_valuation(_stock_verdict(),
                             P.StockReadout(requested=True, error="RuntimeError('boom')"))
        card, _, _ = P.build_valuation_card(v)
        _assert_red(card, P.VALUATION_FAILED_NOW, verb=_RAISED)
        assert dict(P.v2_short_rows(card)[0]), "新出處（逐檔指標）在估值卡要有短句可摘"

    def test_b_no_price_on_record_stays_grey(self, stock_env, monkeypatch):
        stock_env(_ALL_OK, price="none")
        import src.services.valuation_service as VS
        monkeypatch.setattr(VS, "get_stock_dividends",
                            lambda code: VS.StockDividends(avg_div_twd=3.0, paying_years=5,
                                                           years=({"year": 2025, "cash": 3.0},),
                                                           source="FinMind"))
        card, _, _ = _valuation()
        assert card.state == UI_EMPTY and card.note.now == P.VALUATION_EMPTY_NOW
        assert "無股價" in card.note.why


class TestProfitCards:
    @pytest.mark.parametrize("plan", [_ALL_DOWN, _QUOTA_ALL, _IS_FAIL],
                             ids=["down", "quota", "is"])
    def test_a_fetch_failure_reds_all_three(self, stock_env, plan):
        stock_env(plan)
        for (card, facts, _), lab in zip(_profit(), ("毛利率", "營業利益率", "安全邊際")):
            _assert_red(card, P.PROFIT_FAILED_NOW_TEMPLATE.format(label=lab),
                        source=P.SRC_STATEMENTS)
            assert not any("無此股票財報資料" in v for _k, v in facts), (
                "那一句正是把失敗講成「沒有」的原文，⛔ 不得出現在紅卡上")

    def test_b_other_statement_failure_leaves_the_cells_alone(self, stock_env):
        """三格只吃損益表：只有現金流量表沒拿到時三格的數字照畫（⛔ 不連坐）。"""
        stock_env(_CF_FAIL)
        assert [c.state for c, _, _ in _profit()] == [UI_LIVE, UI_LIVE, UI_LIVE]

    @pytest.mark.parametrize("plan", [_NONE, _IS_NONE], ids=["none", "is-none"])
    def test_b_genuinely_none_stays_grey(self, stock_env, plan):
        stock_env(plan)
        assert {c.state for c, _, _ in _profit()} == {UI_EMPTY}


class TestEtfCards:
    @pytest.mark.parametrize("kw,idx,lab", [
        ({"premium": "raise"}, 0, "折溢價"), ({"div": "failed"}, 1, "配息"),
        ({"peer": "nofetch"}, 2, "追蹤／同儕"), ({"peer": "raise"}, 2, "追蹤／同儕")],
        ids=["premium", "dividend", "peer-nofetch", "peer-raise"])
    def test_a_only_the_failed_leg_is_red(self, etf_env, kw, idx, lab):
        etf_env(**kw)
        cards = [b[0] for b in _etf()]
        _assert_red(cards[idx], P.ETF_FAILED_NOW_TEMPLATE.format(label=lab))
        assert [c.state for i, c in enumerate(cards) if i != idx] == [UI_LIVE, UI_LIVE], (
            "另外兩格不是同一次取數的成敗，⛔ 不連坐")

    @pytest.mark.parametrize("kw,idx,now", [
        ({"premium": "none"}, 0, P.PREMIUM_EMPTY_NOW), ({"div": "none"}, 1, P.DIVIDEND_EMPTY_NOW),
        ({"peer": "few"}, 2, P.PEER_EMPTY_NOW)], ids=["no-inav", "no-div", "few-peers"])
    def test_b_genuine_none_stays_grey(self, etf_env, kw, idx, now):
        etf_env(**kw)
        card = _etf()[idx][0]
        assert card.state == UI_EMPTY and card.note.now == now


class TestRedCardsRenderOnTheV2Face:
    """新的 why（「…回報失敗：…」）必須有短句可摘（`V2_SHORT_ROWS`），否則渲染當下轉成紅卡。"""

    def test_every_new_red_note_has_an_excerpt(self, stock_env, etf_env):
        stock_env(_IS_FAIL, price="raise")
        builts = [_health(), _valuation(), *_profit()]
        etf_env(div="failed", premium="raise", peer="nofetch")
        builts += list(_etf())
        for b in builts:
            assert b[0].state == UI_FAILED
            short, full = P.v2_short_rows(b[0])
            assert dict(short)  # 不拋 KeyError
            out = _html(b)
            assert _REPORTED in out


# ══════════════════════════════════════════════════════════════════
# (b) 其他卡、其他頁：一個 byte 都不差
# ══════════════════════════════════════════════════════════════════
#: 把本批 L5 的判定整段中和掉（＝本批之前的行為）。
_REVERT_L5 = (
    ("error=(stock.error or stock.health_error) or None,", "error=stock.error or None,"),
    ("    if _health_err:\n", "    if False:\n"),
    ("    if stock.error or stock.price_error:\n", "    if False:\n"),
    ("    if _fs_failed and (_upstream or DATASET_INCOME_STATEMENT in _fs_failed):\n",
     "    if False:\n"),
    ("error=(etf.error or leg_error) or None,", "error=etf.error or None,"),
    ("None, (_v2_raised(SRC_METRICS), _v2_raised(SRC_METRICS, \"回報失敗\")),\n"
     "           _V2_CHECK_NET)),\n       _v2_rows_for(\"inspect.stock.health\", HEALTH_EMPTY_NOW",
     "None, _v2_raised(SRC_METRICS), _V2_CHECK_NET)),\n"
     "       _v2_rows_for(\"inspect.stock.health\", HEALTH_EMPTY_NOW"),
    ("None, (_v2_raised(SRC_DIVIDENDS), _v2_raised(SRC_357), _v2_raised(SRC_METRICS),\n"
     "                  _v2_raised(SRC_METRICS, \"回報失敗\")), _V2_CHECK_NET)),",
     "None, (_v2_raised(SRC_DIVIDENDS), _v2_raised(SRC_357)), _V2_CHECK_NET)),"),
    ("None, (_v2_raised(SRC_METRICS), _v2_raised(SRC_METRICS, \"回報失敗\")),\n"
     "           _V2_CHECK_NET)) for _k, _l in _V2_ETF_LABELS]",
     "None, _v2_raised(SRC_METRICS), _V2_CHECK_NET)) for _k, _l in _V2_ETF_LABELS]"),
    ("None, (_v2_raised(SRC_STATEMENTS), _v2_raised(SRC_HEALTH),\n"
     "                  _v2_raised(SRC_STATEMENTS, \"回報失敗\")),",
     "None, (_v2_raised(SRC_STATEMENTS), _v2_raised(SRC_HEALTH)),"),
)


def _p03_fingerprints(P_) -> list[tuple[str, str]]:
    """`tests/test_p03_inspect_v2_cards.py` 的窮舉建卡（14 張卡、每一種 readout 組合）→ 逐張雜湊。"""
    from tests import test_p03_inspect_v2_cards as E

    _orig = E.P
    E.P = P_
    try:
        _notes, builts = E._enumerate()
    finally:
        E.P = _orig
    out = []
    for card, facts, sig in builts:
        _k = repr((card, tuple(facts), sig))
        out.append((card.key, hashlib.sha256(
            (_k + P_.v2_card_html(card, facts, sig)).encode()).hexdigest()))
    return out


class TestByteIdentical:
    def test_b_every_enumerated_inspect_card_is_identical_with_or_without_this_batch(self):
        before = _p03_fingerprints(_mutant(P, *_REVERT_L5))
        after = _p03_fingerprints(P)
        assert len(before) == len(after) > 300
        assert len({k for k, _ in after}) == 14
        assert before == after

    @pytest.mark.parametrize("plan,price", [(_NONE, "ok"), (_ALL_OK, "ok"), (_IS_NONE, "none")],
                             ids=["no-statements", "all-ok", "no-is-no-price"])
    def test_b_genuine_stock_results_are_identical(self, stock_env, monkeypatch, plan, price):
        import src.services.valuation_service as VS
        monkeypatch.setattr(VS, "get_stock_dividends", lambda code: VS.StockDividends())
        old = _mutant(P, *_REVERT_L5)
        stock_env(plan, price=price)
        a = [_health(old), _valuation(old), *_profit(old)]
        stock_env(plan, price=price)
        b = [_health(), _valuation(), *_profit()]
        assert [_html(x) for x in a] == [_html(x) for x in b]

    @pytest.mark.parametrize("kw", [{}, {"div": "none"}, {"premium": "none"}, {"peer": "few"}],
                             ids=["all-ok", "no-div", "no-inav", "few-peers"])
    def test_b_genuine_etf_results_are_identical(self, etf_env, kw):
        old = _mutant(P, *_REVERT_L5)
        etf_env(**kw)
        assert [_html(x) for x in _etf(old)] == [_html(x) for x in _etf()]

    def test_b_batch_leaf_does_not_ask_for_failures(self, monkeypatch):
        """葉2 批次表不傳 `failed=`（它不在本批，行為一字不變）。"""
        seen = []

        def _fm(code, kind, **kw):
            seen.append(kw)
            return {}
        monkeypatch.setattr(DS, "fetch_metrics", _fm)
        P._fetch_metrics("2330", "stock")
        assert seen == [{}]

    def test_b_hold_page_path_does_not_ask_for_failures(self, monkeypatch):
        """💼 我的持股 / 推播腳本走 `build_station_rows(metrics_fn=fetch_metrics)`：2 個位置參數。"""
        seen = []

        def _fm(*a, **kw):
            seen.append((a, kw))
            return {"mj_grade": "A", "mj_score_pct": 80, "mj_headline": "", "mj_fail_items": [],
                    "kd_state": None, "current_price": 100.0, "name": "x", "trend_verdict": None}
        DS.build_station_rows([{"ticker": "2330", "asset_kind": T.KIND_STOCK,
                                "asset_class": T.ASSET_SATELLITE}], vix=18.0, metrics_fn=_fm)
        assert seen and all(kw == {} and len(a) == 2 for a, kw in seen)


# ══════════════════════════════════════════════════════════════════
# (c) 突變 —— 拿掉本批任一條新判定，(a) 必須失敗
# ══════════════════════════════════════════════════════════════════
class TestMutations:
    def test_c_l1_without_the_non200_mark_reports_nothing(self, finmind):
        m = _mutant(FFS, ("                _failed_ds[dataset] = (f\"[fetch_fin/{dataset}] 非200回應",
                          "                _unused = (f\"[fetch_fin/{dataset}] 非200回應"))
        finmind(_QUOTA_ALL)
        m._fetch_financial_statements_cached.clear()
        f: dict = {}
        m.fetch_financial_statements("9906", "tok", failed=f)
        assert f == {}, "拿掉之後 (a) 必須抓得到"

    def test_c_l1_without_the_exception_mark_reports_nothing(self, finmind):
        m = _mutant(FFS, ("            _failed_ds[dataset] = f\"[fetch_fin/{dataset}] "
                          "{type(_e).__name__}: {_e}\"",
                          "            pass"))
        finmind(_ALL_DOWN)
        m._fetch_financial_statements_cached.clear()
        f: dict = {}
        m.fetch_financial_statements("9907", "tok", failed=f)
        assert f == {}

    @pytest.mark.parametrize("old,new,plan,price,key", [
        ("            failed[FAILED_STATEMENTS] = \"；\".join(",
         "            _x = \"；\".join(", _QUOTA_ALL, "ok", "statements"),
        ("            failed[FAILED_PRICE] = f\"{type(_e).__name__}: {_e}\"",
         "            pass", _ALL_OK, "raise", "price"),
        ("            else StockDataLoader().get_combined_data(code, 360, True, strict=True))",
         "            else StockDataLoader().get_combined_data(code, 360, True))",
         _ALL_OK, "raise", "price"),
    ], ids=["statements", "price-record", "price-strict"])
    def test_c_l3_stock_marks(self, stock_env, old, new, plan, price, key):
        m = _mutant(DS, (old, new))
        stock_env(plan, price=price)
        f: dict = {}
        m.fetch_metrics("2330", T.KIND_STOCK, failed=f)
        assert key not in f

    @pytest.mark.parametrize("old,new,kw,key", [
        ("                failed[FAILED_DIVIDEND] = str(_div_fail)", "                pass",
         {"div": "failed"}, "dividend"),
        ("                failed[FAILED_PREMIUM] = f\"{type(_e).__name__}: {_e}\"",
         "                pass", {"premium": "raise"}, "premium"),
        ("            failed[FAILED_PEER] = str(_pr.get(\"_err\"))", "            pass",
         {"peer": "nofetch"}, "peer"),
        ("            failed[FAILED_PEER] = f\"{type(_e).__name__}: {_e}\"", "            pass",
         {"peer": "raise"}, "peer"),
    ], ids=["dividend", "premium", "peer-err", "peer-raise"])
    def test_c_l3_etf_marks(self, etf_env, old, new, kw, key):
        m = _mutant(DS, (old, new))
        etf_env(**kw)
        f: dict = {}
        m.fetch_metrics("00878", T.KIND_ETF, failed=f)
        assert key not in f

    def test_c_peer_rule_keyed_on_peer_count(self, etf_env):
        """把「同儕 ≥ 門檻才算失敗」拿掉 → 同儕不足（真的沒有）會被誤報成失敗。"""
        m = _mutant(DS, ("                and len(_pr.get(\"peers\") or ()) >= T.PEER_MIN_GROUP_SIZE):",
                         "                ):"))
        etf_env(peer="few")
        f: dict = {}
        m.fetch_metrics("00878", T.KIND_ETF, failed=f)
        assert "peer" in f, "拿掉之後 (b)「同儕不足照舊灰」必須抓得到"

    def test_c_health_without_the_new_error_is_not_red(self, stock_env):
        m = _mutant(P, ("error=(stock.error or stock.health_error) or None,",
                        "error=stock.error or None,"))
        stock_env(_QUOTA_ALL)
        assert _health(m)[0].state != UI_FAILED

    def test_c_health_without_the_early_return_leaks_a_partial_score(self, stock_env):
        m = _mutant(P, ("    if _health_err:\n", "    if False:\n"))
        stock_env(_CF_FAIL)
        assert _health(m)[0].state == UI_LIVE, "拿掉之後半份財報的分數又被畫成 live"

    def test_c_valuation_without_the_price_gate_is_grey(self, stock_env, monkeypatch):
        import src.services.valuation_service as VS
        monkeypatch.setattr(VS, "get_stock_dividends", lambda code: VS.StockDividends(
            avg_div_twd=3.0, paying_years=5, years=({"year": 2025, "cash": 3.0},),
            source="FinMind"))
        m = _mutant(P, ("    if stock.error or stock.price_error:\n", "    if False:\n"))
        stock_env(_ALL_OK, price="raise")
        card = _valuation(m)[0]
        assert card.state == UI_EMPTY and "無股價" in card.note.why

    def test_c_profit_without_the_gate_is_grey(self, stock_env):
        m = _mutant(P, ("    if _fs_failed and (_upstream or DATASET_INCOME_STATEMENT in _fs_failed):\n",
                        "    if False:\n"))
        stock_env(_QUOTA_ALL)
        assert {c.state for c, _, _ in _profit(m)} == {UI_EMPTY}

    def test_c_profit_gate_needs_the_income_statement_clause(self, stock_env):
        m = _mutant(P, ("    if _fs_failed and (_upstream or DATASET_INCOME_STATEMENT in _fs_failed):\n",
                        "    if _fs_failed and _upstream:\n"))
        stock_env(_IS_FAIL)
        assert {c.state for c, _, _ in _profit(m)} == {UI_EMPTY}

    def test_c_etf_without_the_leg_error_is_grey(self, etf_env):
        m = _mutant(P, ("error=(etf.error or leg_error) or None,", "error=etf.error or None,"))
        etf_env(div="failed")
        assert _etf(m)[1][0].state == UI_EMPTY

    def test_c_short_rows_without_the_new_candidate_raise(self, stock_env):
        m = _mutant(P, ("None, (_v2_raised(SRC_METRICS), _v2_raised(SRC_METRICS, \"回報失敗\")),\n"
                        "           _V2_CHECK_NET)),\n       _v2_rows_for(\"inspect.stock.health\", "
                        "HEALTH_EMPTY_NOW",
                        "None, _v2_raised(SRC_METRICS), _V2_CHECK_NET)),\n"
                        "       _v2_rows_for(\"inspect.stock.health\", HEALTH_EMPTY_NOW"))
        stock_env(_QUOTA_ALL)
        with pytest.raises(KeyError):
            m.v2_short_rows(_health(m)[0])


# ══════════════════════════════════════════════════════════════════
# QA 回合（2026-09-26）：B1 ETF 單腿紅卡的 where ＋ 三個行為測試缺口
# ══════════════════════════════════════════════════════════════════
_FAIL_LOUD_PREFIX = "這一支 L3 對 ETF 是 fail-loud 的（拿不到日線就直接拋）—— "


class TestEtfLegWhere:
    """B1：只有單腿回報失敗時，日線有抓到、L3 沒拋 —— where ⛔ 不得再說「拿不到日線就直接拋」。"""

    @pytest.mark.parametrize("kw,idx", [({"premium": "raise"}, 0), ({"div": "failed"}, 1),
                                        ({"peer": "nofetch"}, 2), ({"peer": "raise"}, 2)],
                             ids=["premium", "dividend", "peer-nofetch", "peer-raise"])
    def test_a_single_leg_red_has_no_fail_loud_prefix(self, etf_env, stock_env, kw, idx):
        etf_env(**kw)
        card = _etf()[idx][0]
        assert card.state == UI_FAILED
        assert _FAIL_LOUD_PREFIX not in card.note.where
        # 剩下的就是健康卡既有 where 的逐字句子（同一則失敗，同一個指路）
        stock_env(_QUOTA_ALL)
        assert card.note.where == _health()[0].note.where
        # 卡面短行不變
        assert dict(P.v2_short_rows(card)[0])[P.V2_GUIDE_FACT_KEY] == P._V2_CHECK_NET

    def test_b_whole_etf_failure_keeps_the_prefix(self):
        e = P.EtfReadout(requested=True, error="RuntimeError('no daily')")
        for card, _f, _s in (P.build_premium_card(e), P.build_dividend_card(e),
                             P.build_peer_card(e)):
            assert card.state == UI_FAILED
            assert card.note.where.startswith(_FAIL_LOUD_PREFIX)
            assert dict(P.v2_short_rows(card)[0])[P.V2_GUIDE_FACT_KEY] == P._V2_CHECK_NET

    def test_b_whole_failure_wins_over_a_leg_error(self):
        e = P.EtfReadout(requested=True, error="RuntimeError('no daily')",
                         dividend_error="ConnectionError: x")
        assert P.build_dividend_card(e)[0].note.where.startswith(_FAIL_LOUD_PREFIX)

    def test_c_mutation_always_prefixing_is_caught(self, etf_env):
        m = _mutant(P, ('            where=(("" if (leg_error and not etf.error) else\n',
                        '            where=(("" if False else\n'))
        etf_env(div="failed")
        assert _etf(m)[1][0].note.where.startswith(_FAIL_LOUD_PREFIX)


class TestProfitUpstreamClause:
    """缺口 1：錯誤 dict（資產負債＋現金流都沒回來）而損益表那一腿**成功** → 仍應紅。

    只有 `_upstream or` 那一條撐得住這一格：`_fs_failed` 裡沒有損益表的 dataset。
    """
    _BS_CF_DOWN = {_BS: _DOWN, _CF: _QUOTA, _IS: _ok(_IS_ROWS)}

    def test_precondition_error_dict_without_an_income_statement_failure(self, finmind):
        finmind(self._BS_CF_DOWN)
        f: dict = {}
        out = FFS.fetch_financial_statements("2330", "tok", failed=f)
        assert "error" in out and set(f) == {_BS, _CF}

    def test_a_error_dict_with_bs_cf_failure_reds_all_three(self, stock_env):
        stock_env(self._BS_CF_DOWN)
        for (card, facts, _), lab in zip(_profit(), ("毛利率", "營業利益率", "安全邊際")):
            _assert_red(card, P.PROFIT_FAILED_NOW_TEMPLATE.format(label=lab),
                        source=P.SRC_STATEMENTS)
            assert not any("無此股票財報資料" in v for _k, v in facts)

    def test_c_mutation_dropping_the_upstream_clause_turns_grey(self, stock_env):
        m = _mutant(P, ("    if _fs_failed and (_upstream or DATASET_INCOME_STATEMENT in _fs_failed):\n",
                        "    if _fs_failed and DATASET_INCOME_STATEMENT in _fs_failed:\n"))
        stock_env(self._BS_CF_DOWN)
        assert UI_FAILED not in {c.state for c, _, _ in _profit(m)}


class TestKdOnlyFailureKeepsValuation:
    """缺口 2：日線到手（有現價）、只有 KD 計算出錯 → ⛔ 不得回報現價失敗，估值卡不得變紅。"""

    @pytest.fixture
    def kd_boom(self, stock_env, monkeypatch):
        import src.compute.strategy.tech_indicators as TI
        import src.services.valuation_service as VS

        def _boom(*_a, **_k):
            raise ValueError("kd boom")
        monkeypatch.setattr(TI, "analyze_kd_state", _boom)
        monkeypatch.setattr(VS, "get_stock_dividends", lambda code: VS.StockDividends(
            avg_div_twd=3.0, paying_years=5, years=({"year": 2025, "cash": 3.0},),
            source="FinMind"))
        stock_env(_ALL_OK, price="ok")

    def test_b_l3_does_not_report_a_price_failure(self, kd_boom):
        f: dict = {}
        m = DS.fetch_metrics("2330", T.KIND_STOCK, failed=f)
        assert m["current_price"] is not None and m["kd_state"] is None, "前提：只有 KD 壞"
        assert DS.FAILED_PRICE not in f

    def test_b_valuation_card_is_not_red(self, kd_boom):
        card = _valuation()[0]
        assert card.state != UI_FAILED, card.note
        assert card.state == UI_LIVE

    def test_c_mutation_dropping_the_price_guard_turns_valuation_red(self, kd_boom):
        m = _mutant(DS, ('        if failed is not None and m["current_price"] is None:'
                         '   # 現價已到手＝只有 KD 壞\n',
                         '        if failed is not None:\n'))
        f: dict = {}
        m.fetch_metrics("2330", T.KIND_STOCK, failed=f)
        assert DS.FAILED_PRICE in f

    def test_c_mutation_end_to_end_the_valuation_card_turns_red(self, kd_boom, monkeypatch):
        m = _mutant(DS, ('        if failed is not None and m["current_price"] is None:'
                         '   # 現價已到手＝只有 KD 壞\n',
                         '        if failed is not None:\n'))
        monkeypatch.setattr(DS, "fetch_metrics", m.fetch_metrics)
        assert _valuation()[0].state == UI_FAILED


def _peer_boundary(monkeypatch, n_peers: int) -> tuple[str, dict]:
    """真的 L2 `compute_etf_peer_ranking` ＋ 真的 L3 `_fetch_peer_ranks`；同儕 `n_peers` 檔、
    批次價格一律抓空 → 回 (L2 的 `_err`, L3 寫進 failed 的內容)。"""
    import src.compute.etf as CE
    import src.data.etf as DE
    monkeypatch.setattr(CE, "get_peers", lambda t: [f"P{i}.TW" for i in range(n_peers)],
                        raising=False)
    monkeypatch.setattr(CE, "get_category_name", lambda t: "x", raising=False)
    monkeypatch.setattr(DE, "fetch_etf_peer_history", lambda tickers, period="2y": pd.DataFrame(),
                        raising=False)
    import src.compute.etf.etf_calc as EC
    # L2 自帶 st.cache_data（以代號為鍵）：每一次探測前清掉，否則第二次拿到的是第一次的結果。
    EC.compute_etf_peer_ranking.clear()
    err = str(EC.compute_etf_peer_ranking("00878.TW").get("_err"))
    f: dict = {}
    DS._fetch_peer_ranks("00878.TW", failed=f)
    return err, f


def _peer_threshold_consistent(monkeypatch) -> bool:
    """L2 寫死的「同儕不足」門檻 ＝ L3 用的 `T.PEER_MIN_GROUP_SIZE`？（在門檻兩側各探一次）"""
    n = T.PEER_MIN_GROUP_SIZE
    below_err, below_f = _peer_boundary(monkeypatch, n - 1)
    at_err, at_f = _peer_boundary(monkeypatch, n)
    return (below_err == "同儕資料不足" and below_f == {}
            and at_err != "同儕資料不足" and DS.FAILED_PEER in at_f)


class TestPeerThresholdIsOneNumber:
    """缺口 3：L2 `len(_peers) < 3` 與 L3 `T.PEER_MIN_GROUP_SIZE` 必須是同一個門檻。

    不一致時會發生的事：門檻之間那幾檔會被 L2 判「同儕不足」卻被 L3 當成抓取失敗
    （或反過來 —— 批次價格抓空被當成同儕不足，灰掉一次真的失敗）。
    """

    @pytest.fixture(autouse=True)
    def _clear_l2_cache(self):
        import src.compute.etf.etf_calc as EC
        yield
        EC.compute_etf_peer_ranking.clear()     # ⛔ 不把替身資料留在 L2 快取給別的測試

    def test_l2_and_l3_agree_on_the_threshold(self, monkeypatch):
        assert _peer_threshold_consistent(monkeypatch)

    @pytest.mark.parametrize("drift", [-1, +1])
    def test_c_changing_only_the_constant_is_caught(self, monkeypatch, drift):
        monkeypatch.setattr(T, "PEER_MIN_GROUP_SIZE", T.PEER_MIN_GROUP_SIZE + drift)
        assert not _peer_threshold_consistent(monkeypatch)

    def test_c_changing_only_the_l2_literal_is_caught(self, monkeypatch):
        import src.compute.etf.etf_calc as EC
        m = _mutant(EC, ("    if len(_peers) < 3:\n", "    if len(_peers) < 4:\n"))
        monkeypatch.setattr(EC, "compute_etf_peer_ranking", m.compute_etf_peer_ranking)
        assert not _peer_threshold_consistent(monkeypatch)
