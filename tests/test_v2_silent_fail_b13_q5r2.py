"""Q5-r2（2026-09-27）：「🔬 查一檔」殘項 —— 抓取失敗 ≠ 真的沒有（Q5 #703 的延續）。

修了哪幾張卡（每張都走該卡**既有**的紅態與 why 組法；⛔ 不新造文案）：

  · `inspect.etf.premium`      L2 `calc_premium_discount` 自己 `except` 吞掉的例外
                               ← L2 `failed=` → L3 `fetch_metrics(failed=)` 的 `FAILED_PREMIUM`
  · `inspect.stock.valuation`  配息備援鏈三段（FinMind／yfinance／TWSE）**都確定抓取失敗**
                               ← L1 `cached_dividends` attrs 旗標 ＋ `fetch_dividend_data(failed=)`
                               → L3 `get_stock_dividends(strict=True)` 拋 `DividendFetchError`
  · `inspect.stock.chips`      三大法人每一段（FinMind raw／TWSE T86／TPEx）**都確定抓取失敗**
                               ← L1 inst fetchers `failed=` → df `attrs[INST_FETCH_FAILED_ATTR]`
                               → L3 `get_chips_readout(strict=True)` 回 `error`

沒修（分不出來，照舊灰，④）：yfinance 回空不拋（配息段、價格段）、ETF NAV 鏈各段回空、
FinMind SDK 回空（production 未安裝 SDK）。

每條路徑：(a) 全失敗 → 紅；(a') 部分失敗 → 照舊（與改前逐 byte 相同）；
(b) 真的沒有 → 與改前逐 byte 相同；(b') 預設呼叫端不變；(c) 突變：拿掉 L5 的 strict／
L3 轉傳／L1 旗標 → (a) 必須失敗。
"""
from __future__ import annotations

import sys
import types

import pandas as pd
import pytest

import src.compute.etf.etf_calc as EC
import src.data.core.data_loader as DL
import src.data.core.data_loader_inst_fetchers as IF
import src.data.proxy.yf_proxy as YP
import src.data.stock.app_stock_fetchers as A
import src.services.dividend_station_service as DS
import src.services.stock_chips_service as CS
import src.services.valuation_service as VS
import tests.test_v2_silent_fail_b6_inspect as B6
from shared.ui_state import UI_EMPTY, UI_FAILED, UI_LIVE
from src.ui.views import page_inspect as P

# b6 的 fixture（不 `from … import *`：會把 b6 的 Test* 類別再收集一次）
finmind = B6.finmind
stock_env = B6.stock_env
etf_env = B6.etf_env

_REAL_PREM = EC.calc_premium_discount
_mutant = B6._mutant
_html = B6._html


def _built_eq(a, b) -> bool:
    return _html(a) == _html(b)


# ══════════════════════════════════════════════════════════════════
# (1) ETF 折溢價：L2 自己吞掉的例外
# ══════════════════════════════════════════════════════════════════
@pytest.fixture
def prem_env(etf_env, monkeypatch):
    """etf_env 其餘兩腿 OK；折溢價改走**真的** L2，其下層由 `mode` 決定。"""
    def _set(mode: str):
        etf_env()
        monkeypatch.setattr(EC, "calc_premium_discount", _REAL_PREM)
        if mode == "raise":
            def _boom(t):
                raise TimeoutError("iNAV relay timeout")
            monkeypatch.setattr(EC, "fetch_etf_official_premium", _boom)
        else:                              # 真的沒有：中繼站未設定、NAV 鏈回空
            monkeypatch.setattr(EC, "fetch_etf_official_premium", lambda t: None)
        monkeypatch.setattr(EC, "fetch_etf_nav_history",
                            lambda t, days=10: pd.DataFrame())
    return _set


_REVERT_DS_PREM = ("            elif failed is not None and _pd_failed:\n",
                   "            elif False:\n")
_REVERT_L2_PREM = ("            failed[PREMIUM_CALC_FAILED_KEY] = f'{type(_ep).__name__}: {_ep}'\n",
                   "            pass\n")


class TestEtfPremium:
    def test_l2_marker_only_on_exception_and_return_unchanged(self, prem_env):
        prem_env("raise")
        f: dict = {}
        out = EC.calc_premium_discount({}, pd.DataFrame(), "00878.TW", failed=f)
        assert set(f) == {EC.PREMIUM_CALC_FAILED_KEY} and "TimeoutError" in f[EC.PREMIUM_CALC_FAILED_KEY]
        assert out == EC.calc_premium_discount({}, pd.DataFrame(), "00878.TW"), "回傳值不變"
        prem_env("none")
        f2: dict = {}
        assert EC.calc_premium_discount({}, pd.DataFrame(), "00878.TW", failed=f2)["premium_pct"] is None
        assert f2 == {}, "所有路徑都沒給 ＝ 分不出來 → 不寫（不猜）"

    def test_a_l2_swallowed_exception_is_red_other_legs_live(self, prem_env):
        prem_env("raise")
        prem, div, peer = B6._etf()
        B6._assert_red(prem[0], P.ETF_FAILED_NOW_TEMPLATE.format(label=prem[0].label))
        assert div[0].state == UI_LIVE and peer[0].state == UI_LIVE
        assert dict(P.v2_short_rows(prem[0])[0])
        P.v2_card_html(*prem)

    def test_b_genuine_none_identical_to_baseline(self, prem_env, monkeypatch):
        prem_env("none")
        new = B6._etf()
        assert new[0][0].state == UI_EMPTY and new[0][0].note.now == P.PREMIUM_EMPTY_NOW
        monkeypatch.setattr(DS, "fetch_metrics", _mutant(DS, _REVERT_DS_PREM).fetch_metrics)
        old = B6._etf()
        assert all(_built_eq(a, b) for a, b in zip(old, new))

    def test_b_default_caller_metrics_unchanged(self, prem_env):
        prem_env("raise")
        m_default = DS.fetch_metrics("00878", "etf")
        f: dict = {}
        m_failed = DS.fetch_metrics("00878", "etf", failed=f)
        assert ({k: repr(v) for k, v in m_default.items()}
                == {k: repr(v) for k, v in m_failed.items()}), "回傳 dict 逐鍵相同"
        assert "premium_pct" not in m_default
        assert DS.FAILED_PREMIUM in f

    def test_c_mutation_l3_forwarding_removed_turns_grey(self, prem_env, monkeypatch):
        prem_env("raise")
        monkeypatch.setattr(DS, "fetch_metrics", _mutant(DS, _REVERT_DS_PREM).fetch_metrics)
        assert B6._etf()[0][0].state == UI_EMPTY

    def test_c_mutation_l2_marker_removed_turns_grey(self, prem_env, monkeypatch):
        prem_env("raise")
        monkeypatch.setattr(EC, "calc_premium_discount",
                            _mutant(EC, _REVERT_L2_PREM).calc_premium_discount)
        assert B6._etf()[0][0].state == UI_EMPTY


# ══════════════════════════════════════════════════════════════════
# (2) 估值卡：配息備援鏈（FinMind／yfinance／TWSE）
# ══════════════════════════════════════════════════════════════════
class _FakeSession:
    def __init__(self, plan):
        self.plan = plan

    def get(self, url, params=None, headers=None, timeout=None):
        key = "twse" if "twse.com.tw" in url else "finmind"
        v = self.plan[key]
        if isinstance(v, Exception):
            raise v
        return B6._Resp(v)


def _fake_finmind_pkg(monkeypatch):
    """讓 `from FinMind.data import DataLoader` 成功（沙箱／production 皆未安裝），REST 才走得到。"""
    class _DL:
        def login_by_token(self, api_token=None):
            pass

        def taiwan_stock_dividend(self, **_k):
            return pd.DataFrame()
    pkg = types.ModuleType("FinMind")
    sub = types.ModuleType("FinMind.data")
    sub.DataLoader = _DL
    pkg.data = sub
    monkeypatch.setitem(sys.modules, "FinMind", pkg)
    monkeypatch.setitem(sys.modules, "FinMind.data", sub)


def _yf_divs(kind: str) -> pd.Series:
    if kind == "ok":
        idx = pd.to_datetime([pd.Timestamp.today() - pd.Timedelta(days=d) for d in (400, 40)])
        return pd.Series([2.0, 2.0], index=idx)
    s = pd.Series(dtype=float)
    if kind == "raise":
        s.attrs[YP.DIVIDENDS_FETCH_FAILED_ATTR] = "YFRateLimitError: Too Many Requests"
    return s                                   # "empty"：yfinance 回空不拋 ＝ 分不出來


@pytest.fixture
def div_env(monkeypatch):
    """`div_env(fm=, yf=, twse=)`：三段各自的行為。fm: 'import'(未安裝＝production)/'down'/'none'。"""
    def _set(fm="import", yf="raise", twse="down"):
        if fm != "import":
            _fake_finmind_pkg(monkeypatch)
        else:
            monkeypatch.setitem(sys.modules, "FinMind", None)
            monkeypatch.setitem(sys.modules, "finmind", None)
        plan = {"finmind": ConnectionError("proxy down") if fm == "down" else {"status": 200, "data": []},
                "twse": ConnectionError("twse down") if twse == "down"
                else {"stat": "很抱歉，沒有符合條件的資料!"}}
        monkeypatch.setattr(A, "_make_proxy_session", lambda: _FakeSession(plan))
        monkeypatch.setattr(A, "_get_finmind_token", lambda: "tok")
        monkeypatch.setattr(YP, "cached_dividends", lambda t: _yf_divs(yf))
        A._fetch_dividend_data_cached.clear()
    yield _set
    A._fetch_dividend_data_cached.clear()


_ALL_DOWN = dict(fm="import", yf="raise", twse="down")
_ALL_DOWN_REST = dict(fm="down", yf="raise", twse="down")
_PARTIAL_YF_EMPTY = dict(fm="import", yf="empty", twse="down")
_PARTIAL_YF_OK = dict(fm="import", yf="ok", twse="down")
_GENUINE_NONE = dict(fm="none", yf="empty", twse="none")

_REVERT_L5_DIV = ("        _div = get_stock_dividends(verdict.code, strict=True)\n",
                  "        _div = get_stock_dividends(verdict.code)\n")
_REVERT_L3_DIV = ("            raise DividendFetchError(\n", "            return StockDividends(); (\n")
_REVERT_L1_YF = ("                _legs[DIVIDEND_LEG_YFINANCE] = str(_yp_fail)\n", "                pass\n")


class TestDividendChain:
    @pytest.mark.parametrize("kw,want", [
        (_ALL_DOWN, set(A.DIVIDEND_LEGS)), (_ALL_DOWN_REST, set(A.DIVIDEND_LEGS)),
        (_PARTIAL_YF_EMPTY, {A.DIVIDEND_LEG_FINMIND, A.DIVIDEND_LEG_TWSE}),
        (_PARTIAL_YF_OK, {A.DIVIDEND_LEG_FINMIND}), (_GENUINE_NONE, set())],
        ids=["all-down", "all-down-rest", "yf-empty", "yf-ok", "genuine-none"])
    def test_l1_only_certain_failures_are_marked(self, div_env, kw, want):
        div_env(**kw)
        f: dict = {}
        out = A.fetch_dividend_data("2330", failed=f)
        assert set(f) == want and all(f.values())
        assert out == A.fetch_dividend_data("2330"), "預設呼叫端拿到同一個 3-tuple"
        assert len(out) == 3

    def test_l1_real_cached_dividends_marks_only_exceptions(self, monkeypatch):
        import yfinance

        class _T:
            def __init__(self, t):
                pass

            @property
            def dividends(self):
                raise ConnectionError("yahoo down")
        monkeypatch.setattr(yfinance, "Ticker", _T)
        YP.cached_dividends.clear()
        try:
            s = YP.cached_dividends("9999.TW")
            assert s.empty and "ConnectionError" in s.attrs[YP.DIVIDENDS_FETCH_FAILED_ATTR]

            class _E(_T):
                @property
                def dividends(self):
                    return pd.Series(dtype=float)
            monkeypatch.setattr(yfinance, "Ticker", _E)
            YP.cached_dividends.clear()
            s2 = YP.cached_dividends("9999.TW")
            assert s2.empty and YP.DIVIDENDS_FETCH_FAILED_ATTR not in s2.attrs
        finally:
            YP.cached_dividends.clear()

    @pytest.mark.parametrize("kw", [_ALL_DOWN, _ALL_DOWN_REST], ids=["import", "rest"])
    def test_a_all_three_certainly_failed_is_red(self, stock_env, div_env, kw):
        stock_env(B6._ALL_OK)
        div_env(**kw)
        card, facts, sig = B6._valuation()
        B6._assert_red(card, P.VALUATION_FAILED_NOW, source=P.SRC_DIVIDENDS, verb=B6._RAISED)
        assert "DividendFetchError" in card.note.why and sig == ""
        assert dict(P.v2_short_rows(card)[0])
        P.v2_card_html(card, facts, sig)

    @pytest.mark.parametrize("kw", [_PARTIAL_YF_EMPTY, _PARTIAL_YF_OK, _GENUINE_NONE],
                             ids=["yf-empty(④)", "yf-ok", "genuine-none"])
    def test_b_partial_or_genuine_identical_to_baseline(self, stock_env, div_env, kw):
        old = _mutant(P, _REVERT_L5_DIV)
        stock_env(B6._ALL_OK)
        div_env(**kw)
        a = B6._valuation(old)
        stock_env(B6._ALL_OK)
        div_env(**kw)
        b = B6._valuation()
        assert b[0].state != UI_FAILED
        assert _built_eq(a, b)

    def test_b_default_l3_caller_does_not_raise(self, div_env):
        div_env(**_ALL_DOWN)
        d = VS.get_stock_dividends("2330")
        assert d == VS.StockDividends(), "預設（strict=False）照舊回「沒有紀錄」"
        with pytest.raises(VS.DividendFetchError):
            VS.get_stock_dividends("2330", strict=True)

    def test_c_mutation_l5_without_strict_turns_grey(self, stock_env, div_env):
        old = _mutant(P, _REVERT_L5_DIV)
        stock_env(B6._ALL_OK)
        div_env(**_ALL_DOWN)
        assert B6._valuation(old)[0].state == UI_EMPTY

    def test_c_mutation_l3_without_raise_turns_grey(self, stock_env, div_env, monkeypatch):
        monkeypatch.setattr(VS, "get_stock_dividends",
                            _mutant(VS, _REVERT_L3_DIV).get_stock_dividends)
        stock_env(B6._ALL_OK)
        div_env(**_ALL_DOWN)
        assert B6._valuation()[0].state == UI_EMPTY

    def test_c_mutation_l1_without_yf_marker_turns_grey(self, stock_env, div_env, monkeypatch):
        m = _mutant(A, _REVERT_L1_YF)
        stock_env(B6._ALL_OK)
        div_env(**_ALL_DOWN)
        monkeypatch.setattr(A, "fetch_dividend_data", m.fetch_dividend_data)
        try:
            assert B6._valuation()[0].state == UI_EMPTY
        finally:
            m._fetch_dividend_data_cached.clear()


# ══════════════════════════════════════════════════════════════════
# (3) 籌碼卡：三大法人那一腿（FinMind raw／TWSE T86／TPEx）
# ══════════════════════════════════════════════════════════════════
def _yf_price_frame(*_a, **_k) -> pd.DataFrame:
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=300, name="Date")
    px = [100.0 + (i % 7) for i in range(len(idx))]
    return pd.DataFrame({"Open": px, "High": [p + 1 for p in px], "Low": [p - 1 for p in px],
                         "Close": px, "Volume": [5_000_000] * len(idx)}, index=idx)


class _FmSess:
    def __init__(self, v):
        self.v = v

    def get(self, *_a, **_k):
        if isinstance(self.v, Exception):
            raise self.v
        return B6._Resp(self.v)


@pytest.fixture
def chips_env(monkeypatch):
    """`chips_env(fm=, twse=, tpex=)`：fm 'down'/'quota'/'none'；twse/tpex 'down'/'none'。"""
    def _day(cache_name, mode):
        def _get(ds):
            if mode == "none":             # 有回答（例如假日／沒有這一檔）→ 進日快取
                getattr(IF, cache_name)[ds] = {}
            return {}                      # "down"：網路失敗 → 不進日快取
        return _get

    def _set(fm="down", twse="down", tpex="down"):
        monkeypatch.setattr(DL, "_yf_dl", _yf_price_frame)
        monkeypatch.setattr(DL, "get_stock_name", lambda sid: "測試股")
        monkeypatch.setattr(DL, "_fetch_finmind_margin_raw", lambda sid, df, s: (df, "missing"))
        v = {"down": ConnectionError("proxy down"),
             "quota": {"status": 402, "msg": "Requests reach the upper limit"},
             "none": {"status": 200, "data": []}}[fm]
        monkeypatch.setattr(DL, "_bps_dl", lambda: _FmSess(v))
        monkeypatch.setattr(IF, "_T86_DAY_CACHE", {})
        monkeypatch.setattr(IF, "_TPEX_DAY_CACHE", {})
        monkeypatch.setattr(IF, "_get_t86_day", _day("_T86_DAY_CACHE", twse))
        monkeypatch.setattr(IF, "_get_tpex_day", _day("_TPEX_DAY_CACHE", tpex))
        loader = DL.StockDataLoader.__new__(DL.StockDataLoader)
        loader.dl = None                   # production：FinMind SDK 未安裝（requirements v19.79）
        monkeypatch.setattr(A, "_get_loader", lambda *a, **k: loader)
        monkeypatch.setattr(A, "_load_cache", lambda *a, **k: None)
        monkeypatch.setattr(A, "_save_cache", lambda *a, **k: None)
        DL.StockDataLoader._get_combined_data_cached.clear()
        A.fetch_price_data.clear()
        return loader
    yield _set
    DL.StockDataLoader._get_combined_data_cached.clear()
    A.fetch_price_data.clear()


def _chips(P_=P):
    req = P.InspectRequest(submitted=True, ticker="2330", period_days=120)
    return P_.build_chips_card(P_.load_chips(B6._stock_verdict(), req))


_ALL_INST_DOWN = dict(fm="down", twse="down", tpex="down")
_ALL_INST_DOWN_Q = dict(fm="quota", twse="down", tpex="down")
_PARTIAL_INST = dict(fm="quota", twse="down", tpex="none")
_GENUINE_INST_NONE = dict(fm="none", twse="none", tpex="none")

_REVERT_L5_CHIPS = ("        _c = get_chips_readout(verdict.code, days=req.period_days, strict=True)\n",
                    "        _c = get_chips_readout(verdict.code, days=req.period_days)\n")
_REVERT_L1_TWSE = ("            failed['twse'] = f'[TWSE T86] {stock_id} 失敗: {\",\".join(_asked)}'\n",
                   "            pass\n")


class TestChips:
    @pytest.mark.parametrize("kw,flagged", [
        (_ALL_INST_DOWN, True), (_ALL_INST_DOWN_Q, True),
        (_PARTIAL_INST, False), (_GENUINE_INST_NONE, False)],
        ids=["all-down", "quota+down", "partial", "genuine-none"])
    def test_l1_attrs_flag_only_when_every_leg_certainly_failed(self, chips_env, kw, flagged):
        loader = chips_env(**kw)
        df, err, _ = loader.get_combined_data("2330", 180, True)
        assert err is None and "外資" not in df.columns and df.attrs["inst_src"] == "missing"
        assert (DL.INST_FETCH_FAILED_ATTR in df.attrs) is flagged
        if flagged:
            assert all(k in df.attrs[DL.INST_FETCH_FAILED_ATTR] for k in ("FM-Raw", "TWSE T86", "TPEx"))

    @pytest.mark.parametrize("kw", [_ALL_INST_DOWN, _ALL_INST_DOWN_Q], ids=["down", "quota"])
    def test_a_every_inst_leg_failed_is_red(self, chips_env, kw):
        chips_env(**kw)
        card, facts, sig = _chips()
        B6._assert_red(card, P.CHIPS_FAILED_NOW, source=P.SRC_CHIPS)
        assert sig == "" and dict(P.v2_short_rows(card)[0])
        P.v2_card_html(card, facts, sig)

    @pytest.mark.parametrize("kw", [_PARTIAL_INST, _GENUINE_INST_NONE], ids=["partial", "genuine-none"])
    def test_b_partial_or_genuine_identical_to_baseline(self, chips_env, kw):
        old = _mutant(P, _REVERT_L5_CHIPS)
        chips_env(**kw)
        a = _chips(old)
        chips_env(**kw)
        b = _chips()
        assert b[0].state == UI_EMPTY and _built_eq(a, b)

    def test_b_default_l3_caller_unchanged(self, chips_env):
        chips_env(**_ALL_INST_DOWN)
        r = CS.get_chips_readout("2330", days=120)
        assert r.error == "" and r.miss_reason, "預設（strict=False）照舊是「判不出來」"
        r2 = CS.get_chips_readout("2330", days=120, strict=True)
        assert r2.error and not r2.miss_reason

    def test_c_mutation_l5_without_strict_turns_grey(self, chips_env):
        old = _mutant(P, _REVERT_L5_CHIPS)
        chips_env(**_ALL_INST_DOWN)
        assert _chips(old)[0].state == UI_EMPTY

    def test_c_mutation_l1_without_twse_marker_is_not_flagged(self, chips_env, monkeypatch):
        m = _mutant(IF, _REVERT_L1_TWSE)
        chips_env(**_ALL_INST_DOWN)
        monkeypatch.setattr(DL, "_fetch_twse_inst_fallback", m._fetch_twse_inst_fallback)
        monkeypatch.setattr(m, "_get_t86_day", IF._get_t86_day)
        monkeypatch.setattr(m, "_T86_DAY_CACHE", IF._T86_DAY_CACHE)
        assert _chips()[0].state == UI_EMPTY
