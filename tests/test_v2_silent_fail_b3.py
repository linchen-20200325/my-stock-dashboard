"""批次 3：「💼 我的持股」配息卡 `hold.deep.dividend_cash` —— 「抓不到配息」與「真的沒配息」必須分得開。

（客戶 2026-09-26 授權本批改 L1 `fetch_etf_dividends` 這一支，以及本卡判定所需的 L3／L5。）

根因：L1 `fetch_etf_dividends` 是 `@st.cache_data`，例外在函式**內**被吞成空 Series ——
(1) 與「真的沒配息」長得一模一樣；(2) 那個空 Series 被快取一小時（違 §1.A-3(a)）。
L3 於是把抓取失敗的代號列進 `no_payout_tickers`，L5 畫出灰卡「這是一個有效的結果」。

每條失敗路徑三件事（同批次 1／2）：
  (a) 上游失敗 → 紅卡 `CASH_FAILED_NOW`；⛔ 不得是灰卡「近一年查不到任何一筆配息」，
      ⛔ 不得是 live 的部分總額，⛔ 失敗的代號不得列在「貢獻 0 元」；
  (b) 真的 0 → 原封不動；
  (c) 突變：拿掉本批新加的那一條判定 → (a) 必須失敗。

⚠️ yfinance **沒拋例外、只回空的 `.dividends`** 仍然分不出來（照舊當「沒配息」）——
本檔 `TestL1.test_b_empty_without_exception_is_still_no_dividends` 把這個限制釘住。
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import pathlib
import sys
import types

import pandas as pd
import pytest

import src.data.etf.etf_fetch as F
import src.services.dividend_tax_service as DTS
import src.services.portfolio_deep_service as PDS
from shared.station_specs import MISS_FETCH_FAILED, MISS_TEXT
from shared.ui_state import UI_EMPTY, UI_FAILED, UI_LIVE
from src.services.portfolio_deep_service import DividendCashResult
from src.ui.views import page_hold as PH


def _mutant(mod: types.ModuleType, old: str, new: str) -> types.ModuleType:
    """把 `mod` 的原始碼裡**恰好一處** `old` 換成 `new`，載成一個獨立的新模組。"""
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    assert src.count(old) == 1, f"突變點不唯一或已不存在：{old!r}"
    name = f"_mutant_b3_{mod.__name__.rsplit('.', 1)[-1]}"
    spec = importlib.util.spec_from_loader(name, loader=None)
    m = importlib.util.module_from_spec(spec)
    m.__file__ = mod.__file__
    sys.modules[name] = m
    try:
        exec(compile(src.replace(old, new), mod.__file__, "exec"), m.__dict__)
    finally:
        sys.modules.pop(name, None)
    return m


def _recent(n: int = 4, per_share: float = 1.0) -> pd.Series:
    today = pd.Timestamp(dt.date.today())
    return pd.Series([per_share] * n,
                     index=pd.DatetimeIndex([today - pd.Timedelta(days=60 * i)
                                             for i in range(n)]))


class _FakeYf:
    """假的 `yf.Ticker`：依 `script` 逐次回應（`Exception` 實例 → 拋出）。記錄打了幾次。"""

    def __init__(self, script):
        self.script = list(script)
        self.calls: list[str] = []

    def __call__(self, ticker):
        self.calls.append(ticker)
        step = self.script.pop(0)

        class _T:
            @property
            def dividends(self_inner):
                if isinstance(step, Exception):
                    raise step
                return step.copy()
        return _T()


@pytest.fixture(autouse=True)
def _clear_l1_cache():
    F._fetch_etf_dividends_cached.clear()
    F._dividends_fail_until.clear()
    F._dividends_success_gen.clear()
    yield
    F._fetch_etf_dividends_cached.clear()
    F._dividends_fail_until.clear()
    F._dividends_success_gen.clear()


class _Clock:
    """假的 `time` 模組（只給 L1 退避用的 `monotonic`）。"""

    def __init__(self, t: float = 1000.0):
        self.t = t

    def monotonic(self) -> float:
        return self.t


# ══════════════════════════════════════════════════════════════════
# L1 `fetch_etf_dividends`
# ══════════════════════════════════════════════════════════════════
class TestL1:
    def test_a_failure_sets_the_flag_and_still_looks_empty_to_old_callers(self, monkeypatch):
        monkeypatch.setattr(F.yf, "Ticker", _FakeYf([RuntimeError("HTTP 429")]))
        s = F.fetch_etf_dividends("B3FAIL.TW")
        assert isinstance(s, pd.Series) and len(s) == 0 and s.empty
        assert s.dtype == float
        assert s.attrs[F.DIVIDENDS_FETCH_FAILED_ATTR] == "RuntimeError: HTTP 429"

    def test_a_failure_is_not_cached_retries_after_the_cooldown(self, monkeypatch):
        clock = _Clock()
        monkeypatch.setattr(F, "_time_div", clock)
        fake = _FakeYf([RuntimeError("HTTP 429"), _recent()])
        monkeypatch.setattr(F.yf, "Ticker", fake)
        first = F.fetch_etf_dividends("B3RETRY.TW")
        clock.t += F._DIVIDENDS_FAIL_COOLDOWN_SEC + 1
        second = F.fetch_etf_dividends("B3RETRY.TW")
        assert len(fake.calls) == 2, "失敗被快取了 —— 退避過後沒有重抓（§1.A-3(a)）"
        assert F.DIVIDENDS_FETCH_FAILED_ATTR in first.attrs
        assert len(second) == 4
        assert F.DIVIDENDS_FETCH_FAILED_ATTR not in second.attrs

    def test_a_within_the_cooldown_there_is_no_refetch_and_one_log(self, monkeypatch, capsys):
        clock = _Clock()
        monkeypatch.setattr(F, "_time_div", clock)
        fake = _FakeYf([RuntimeError("HTTP 429"), _recent()])
        monkeypatch.setattr(F.yf, "Ticker", fake)
        outs = [F.fetch_etf_dividends("B3COOL.TW")]
        for _ in range(3):
            clock.t += F._DIVIDENDS_FAIL_COOLDOWN_SEC / 4
            outs.append(F.fetch_etf_dividends("B3COOL.TW"))
        assert len(fake.calls) == 1, "退避期間又打了 Yahoo（§1.A-3(b)）"
        assert all(o.empty and o.attrs[F.DIVIDENDS_FETCH_FAILED_ATTR] == "RuntimeError: HTTP 429"
                   for o in outs)
        assert capsys.readouterr().out.count("無法取得 B3COOL.TW 配息") == 1
        assert 120 <= F._DIVIDENDS_FAIL_COOLDOWN_SEC <= 300

    def test_a_cooldown_is_per_ticker(self, monkeypatch):
        monkeypatch.setattr(F, "_time_div", _Clock())
        fake = _FakeYf([RuntimeError("HTTP 429"), _recent()])
        monkeypatch.setattr(F.yf, "Ticker", fake)
        F.fetch_etf_dividends("B3A.TW")
        assert len(F.fetch_etf_dividends("B3B.TW")) == 4
        assert fake.calls == ["B3A.TW", "B3B.TW"]

    def test_b_success_clears_the_cooldown_entry(self, monkeypatch):
        clock = _Clock()
        monkeypatch.setattr(F, "_time_div", clock)
        fake = _FakeYf([RuntimeError("HTTP 429"), _recent()])
        monkeypatch.setattr(F.yf, "Ticker", fake)
        F.fetch_etf_dividends("B3CLR.TW")
        assert "B3CLR.TW" in F._dividends_fail_until
        clock.t += F._DIVIDENDS_FAIL_COOLDOWN_SEC + 1
        F.fetch_etf_dividends("B3CLR.TW")
        assert "B3CLR.TW" not in F._dividends_fail_until

    @staticmethod
    def _interleave(mod, monkeypatch):
        """確定性重現競態：A 的抓取進行中（尚未拋出）→ B 抓到並成功 → A 才拋出。

        以替身取代快取層（不經 `st.cache_data`，避免同鍵重入），B 在 A 的抓取裡同步呼叫。
        """
        state = {"n": 0}

        def _inner(ticker):
            state["n"] += 1
            if state["n"] == 1:                                   # 執行緒 A
                state["b"] = mod.fetch_etf_dividends(ticker)      # 執行緒 B 插隊成功
                raise RuntimeError("HTTP 429")
            return _recent()

        monkeypatch.setattr(mod, "_fetch_etf_dividends_cached", _inner)
        monkeypatch.setattr(mod, "_time_div", _Clock())
        a = mod.fetch_etf_dividends("B3RACE.TW")
        c = mod.fetch_etf_dividends("B3RACE.TW")                  # 下一位
        return a, state, c

    def test_a_a_late_failure_does_not_override_a_concurrent_success(self, monkeypatch):
        a, state, c = self._interleave(F, monkeypatch)
        assert F.DIVIDENDS_FETCH_FAILED_ATTR in a.attrs           # A 自己照實回失敗
        assert len(state["b"]) == 4                               # B 成功
        assert "B3RACE.TW" not in F._dividends_fail_until
        assert F.DIVIDENDS_FETCH_FAILED_ATTR not in c.attrs and len(c) == 4
        assert state["n"] == 3                                    # 下一位真的去抓（非退避）

    def test_c_mutation_dropping_the_generation_check_freezes_a_false_failure(self, monkeypatch):
        m = _mutant(F, "            if _dividends_success_gen.get(ticker, 0) == _gen:"
                       "   # 期間沒有人成功過才記\n",
                    "            if True:\n")
        _a, _state, c = self._interleave(m, monkeypatch)
        assert c.attrs.get(F.DIVIDENDS_FETCH_FAILED_ATTR) == "RuntimeError: HTTP 429"

    def test_c_mutation_dropping_the_cooldown_hits_yahoo_every_call(self, monkeypatch):
        m = _mutant(F, "    if _prev is not None and _now - _prev[0] < _DIVIDENDS_FAIL_COOLDOWN_SEC:\n",
                    "    if False:\n")
        m._fetch_etf_dividends_cached.clear()
        fake = _FakeYf([RuntimeError("a"), RuntimeError("b"), RuntimeError("c")])
        monkeypatch.setattr(F.yf, "Ticker", fake)
        for _ in range(3):
            m.fetch_etf_dividends("B3MUTC.TW")
        assert len(fake.calls) == 3

    def test_b_success_is_unchanged_and_cached(self, monkeypatch):
        tz = _recent().tz_localize("UTC")
        fake = _FakeYf([tz])
        monkeypatch.setattr(F.yf, "Ticker", fake)
        a = F.fetch_etf_dividends("B3OK.TW")
        b = F.fetch_etf_dividends("B3OK.TW")
        assert len(fake.calls) == 1, "成功結果應該照舊被快取"
        assert a.index.tz is None and len(a) == 4
        assert a.attrs["source"] == "Yahoo:B3OK.TW:dividends" and "fetched_at" in a.attrs
        assert F.DIVIDENDS_FETCH_FAILED_ATTR not in a.attrs
        pd.testing.assert_series_equal(a, b)

    def test_b_empty_without_exception_is_still_no_dividends(self, monkeypatch):
        """已知限制：yfinance 沒拋例外、只回空序列 → 分不出來，不猜。"""
        monkeypatch.setattr(F.yf, "Ticker", _FakeYf([pd.Series(dtype=float)]))
        s = F.fetch_etf_dividends("B3EMPTY.TW")
        assert s.empty and F.DIVIDENDS_FETCH_FAILED_ATTR not in s.attrs

    def test_the_public_function_is_not_cached(self):
        """`attrs` 旗標不經過快取序列化，而且失敗不會被凍住 —— 公開函式本身不能掛快取。"""
        assert not hasattr(F.fetch_etf_dividends, "clear")
        assert hasattr(F._fetch_etf_dividends_cached, "clear")

    def test_c_mutation_swallowing_inside_the_cache_freezes_the_failure(self, monkeypatch):
        m = _mutant(F, "        divs = yf.Ticker(ticker).dividends\n    if divs.empty:",
                    "        try:\n            divs = yf.Ticker(ticker).dividends\n"
                    "        except Exception:\n            divs = pd.Series(dtype=float)\n"
                    "    if divs.empty:")
        m._fetch_etf_dividends_cached.clear()
        fake = _FakeYf([RuntimeError("HTTP 429"), _recent()])
        monkeypatch.setattr(F.yf, "Ticker", fake)
        first = m.fetch_etf_dividends("B3MUT.TW")
        m.fetch_etf_dividends("B3MUT.TW")
        assert len(fake.calls) == 1                         # 修前行為：失敗被凍住
        assert F.DIVIDENDS_FETCH_FAILED_ATTR not in first.attrs


# ══════════════════════════════════════════════════════════════════
# 其他 caller：輸出不變
# ══════════════════════════════════════════════════════════════════
class TestOtherCallersUnchanged:
    def test_dividend_tax_view_keeps_its_existing_keys_and_values(self, monkeypatch):
        """`etf_tab_portfolio` 用的 `get_dividend_tax_view`：既有鍵的值與修前一致，只多一個鍵。"""
        monkeypatch.setattr(DTS, "holding_currency", lambda t: "TWD")
        monkeypatch.setattr(F.yf, "Ticker", _FakeYf([RuntimeError("boom")]))
        v = DTS.get_dividend_tax_view([{"ticker": "B3X.TW", "shares": 1000}])
        assert v["per_etf"] == [{"代號": "B3X.TW", "幣別": "TWD", "近1年稅前配息": 0,
                                 "二代健保": 0, "配息筆數": 0}]
        assert v["overseas"] == [] and v["n_tw"] == 1
        assert v["summary"]["gross"] == 0
        assert set(v) == {"summary", "per_etf", "overseas", "n_tw", "fetch_failed"}
        # 舊的 per-ticker helper 簽章與回傳型別不變
        assert DTS._recent_payments_twd("B3X.TW", 1000) == []

    def test_plain_series_from_a_stub_means_no_failure(self, monkeypatch):
        """既有測試替身回沒有 attrs 的 Series / None → 沒有失敗標記（行為同修前）。"""
        monkeypatch.setattr(DTS, "holding_currency", lambda t: "TWD")
        for stub in (lambda t: None, lambda t: pd.Series(dtype=float)):
            monkeypatch.setattr(DTS, "fetch_etf_dividends", stub)
            v = DTS.get_dividend_tax_view([{"ticker": "A.TW", "shares": 1000}])
            assert v["fetch_failed"] == {}


# ══════════════════════════════════════════════════════════════════
# L3 `get_dividend_cash_flow`
# ══════════════════════════════════════════════════════════════════
def _row(code: str, lots: float = 1.0) -> dict:
    return {"代號": code, "held": True, "張數": lots, "均價": 20.0, "現價": 40.0,
            "_detail": {}}


def _prices():
    idx = pd.bdate_range("2025-01-02", periods=60)
    return pd.DataFrame({"Close": [100.0 + (i % 5) for i in range(60)]}, index=idx)


def _l3(monkeypatch, divs: dict, mod=PDS):
    """真的 L3 → 真的 L1（`yf.Ticker` 換成按代號回應的替身）。

    後綴判定：`divs` 的鍵是哪個後綴，`fetch_etf_price` 就只對那個後綴有價
    （`.TWO` 鍵 → `.TW` 抓空、`.TWO` 有價 → L3 改用 `.TWO`）。
    """
    monkeypatch.setattr("src.data.etf.etf_fetch.fetch_etf_price",
                        lambda t, period="1y": _prices() if t in divs else pd.DataFrame())
    monkeypatch.setattr(DTS, "holding_currency", lambda t: "TWD")

    def _ticker(tk):
        step = divs[tk]

        class _T:
            @property
            def dividends(self):
                if isinstance(step, Exception):
                    raise step
                return step.copy()
        return _T()

    monkeypatch.setattr(F.yf, "Ticker", _ticker)
    return mod.get_dividend_cash_flow([_row(c.split(".")[0]) for c in divs])


class TestL3:
    def test_a_failed_ticker_is_marked_and_not_listed_as_no_payout(self, monkeypatch):
        res = _l3(monkeypatch, {"0056.TW": RuntimeError("HTTP 429")})
        assert res.failed_tickers == ("0056.TW",)
        assert res.no_payout_tickers == ()

    def test_a_partial_failure_is_marked_next_to_a_good_ticker(self, monkeypatch):
        res = _l3(monkeypatch, {"0056.TW": _recent(), "00878.TW": RuntimeError("x")})
        assert res.failed_tickers == ("00878.TW",)
        assert res.payouts_n == 4 and res.no_payout_tickers == ()

    def test_a_otc_failure_is_reported_under_the_rows_own_ticker(self, monkeypatch):
        res = _l3(monkeypatch, {"6488.TWO": RuntimeError("HTTP 429")})
        assert res.failed_tickers == ("6488.TW",)
        assert res.failed_detail == ("6488.TW: RuntimeError: HTTP 429",)
        assert "6488.TW" not in res.no_payout_tickers and "6488.TWO" not in res.no_payout_tickers
        card = PH.build_dividend_cash_card(_deep(res))[0]
        assert card.state == UI_FAILED
        assert "6488.TW: RuntimeError: HTTP 429" in card.note.why
        assert "6488.TWO" not in card.note.why

    def test_c_mutation_skipping_the_suffix_mapback_is_caught(self, monkeypatch):
        m = _mutant(PDS, "    _fail_by_id = {str(_back.get(str(_t), str(_t))): str(_m)\n",
                    "    _fail_by_id = {str(_t): str(_m)\n")
        res = _l3(monkeypatch, {"6488.TWO": RuntimeError("HTTP 429")}, mod=m)
        assert res.failed_tickers == ("6488.TWO",)          # 身分沒換回
        assert res.no_payout_tickers == ("6488.TW",)        # 又被列成「貢獻 0 元」

    def test_b_genuine_no_payout_is_unchanged(self, monkeypatch):
        res = _l3(monkeypatch, {"0056.TW": pd.Series(dtype=float)})
        assert res.failed_tickers == ()
        assert res.no_payout_tickers == ("0056.TW",)
        assert res.computed and res.payouts_n == 0

    def test_b_missing_key_from_an_old_upstream_means_no_failures(self, monkeypatch):
        monkeypatch.setattr("src.data.etf.etf_fetch.fetch_etf_price",
                            lambda t, period="1y": _prices())
        monkeypatch.setattr(
            "src.services.dividend_tax_service.get_dividend_tax_view",
            lambda h, *, marginal_rate=None: {
                "summary": {"gross": 0, "nhi_premium": 0, "net_after_nhi": 0},
                "per_etf": [{"代號": "0056.TW", "配息筆數": 0}], "overseas": [], "n_tw": 1})
        res = PDS.get_dividend_cash_flow([_row("0056")])
        assert res.failed_tickers == () and res.no_payout_tickers == ("0056.TW",)

    def test_c_mutation_dropping_the_l3_marker_hides_the_failure(self, monkeypatch):
        m = _mutant(DTS, "        if _fail:\n", "        if False:\n")
        monkeypatch.setattr(DTS, "get_dividend_tax_view", m.get_dividend_tax_view)
        monkeypatch.setattr(m, "holding_currency", lambda t: "TWD")
        res = _l3(monkeypatch, {"0056.TW": RuntimeError("HTTP 429")})
        assert res.failed_tickers == ()
        assert res.no_payout_tickers == ("0056.TW",)                # 修前的謊

    def test_c_mutation_dropping_the_no_payout_exclusion_leaks_again(self, monkeypatch):
        m = _mutant(PDS, '                                and str(_p.get("代號")) not in _failed),\n',
                    "                                ),\n")
        res = _l3(monkeypatch, {"0056.TW": RuntimeError("HTTP 429")}, mod=m)
        assert res.no_payout_tickers == ("0056.TW",)


# ══════════════════════════════════════════════════════════════════
# L5 配息卡
# ══════════════════════════════════════════════════════════════════
def _cash(**kw) -> DividendCashResult:
    kw.setdefault("computed", True)
    kw.setdefault("coverage_pct", 100.0)
    kw.setdefault("gross_twd", 30000.0)
    kw.setdefault("net_after_nhi_twd", 30000.0)
    kw.setdefault("payouts_n", 8)
    kw.setdefault("tw_n", 2)
    kw.setdefault("lots_n", 2)
    kw.setdefault("held_n", 2)
    kw.setdefault("shares_total", 3000.0)
    return DividendCashResult(**kw)


def _deep(cash, **kw) -> PH.DeepReadout:
    return PH.DeepReadout(requested=True, submitted=True, bound=True, holdings_n=2,
                          has_station_rows=True, cash=cash, **kw)


class TestL5Card:
    def test_a_all_failed_is_red_not_the_valid_empty(self):
        d = _deep(_cash(gross_twd=0.0, net_after_nhi_twd=0.0, payouts_n=0,
                        failed_tickers=("0056",),
                        failed_detail=("0056: RuntimeError: HTTP 429",)))
        card, facts, _ = PH.build_dividend_cash_card(d)
        assert card.state == UI_FAILED
        # 走本卡既有的 error 分支，error ＝ L1 的失敗訊息（畫面照實印出來）
        assert card.note == PH._deep_note(d, now=PH.CASH_FAILED_NOW, source=PH.SRC_DIV_CASH,
                                          error="0056: RuntimeError: HTTP 429")
        assert "0056: RuntimeError: HTTP 429" in card.note.why
        assert "若只有這一格紅、其餘幾格正常" in card.note.where
        assert MISS_TEXT[MISS_FETCH_FAILED].removeprefix("這一檔") not in card.note.why
        assert card.note.where != PH.STATION_ERROR_WHERE
        assert "有效的結果" not in card.note.why
        assert not any("貢獻 0 元" in k for k, _ in facts)

    def test_a_partial_failure_is_red_not_a_live_partial_total(self):
        card, _facts, badge = PH.build_dividend_cash_card(_deep(_cash(
            failed_tickers=("0056", "00878"),
            failed_detail=("0056: RuntimeError: a", "00878: TimeoutError: b"))))
        assert card.state == UI_FAILED and card.value in (None, "")
        assert card.note.now == PH.CASH_FAILED_NOW
        assert "0056: RuntimeError: a；00878: TimeoutError: b" in card.note.why
        assert badge == ""

    def test_a_end_to_end_l1_failure_turns_the_card_red(self, monkeypatch):
        res = _l3(monkeypatch, {"0056.TW": RuntimeError("HTTP 429")})
        card, _f, _b = PH.build_dividend_cash_card(_deep(res))
        assert card.state == UI_FAILED and card.note.now == PH.CASH_FAILED_NOW

    def test_b_genuine_no_payout_is_unchanged(self):
        card, facts, _ = PH.build_dividend_cash_card(_deep(_cash(
            gross_twd=0.0, net_after_nhi_twd=0.0, payouts_n=0,
            no_payout_tickers=("0056",))))
        assert card.state == UI_EMPTY and card.note.now == PH.CASH_NO_PAYOUT_NOW
        assert card.note.why.startswith("**這是一個有效的結果**")
        assert any("貢獻 0 元" in k for k, _ in facts)

    def test_b_clean_result_is_still_live(self):
        card, _f, badge = PH.build_dividend_cash_card(_deep(_cash()))
        assert card.state == UI_LIVE and badge == "不含綜所稅"

    def test_b_the_exception_path_keeps_its_own_note(self):
        d = _deep(_cash(failed_tickers=("0056",)), cash_error="RuntimeError('x')")
        card, _f, _b = PH.build_dividend_cash_card(d)
        assert card.state == UI_FAILED
        assert card.note == PH._deep_note(d, now=PH.CASH_FAILED_NOW, source=PH.SRC_DIV_CASH,
                                          error="RuntimeError('x')")

    def test_b_the_short_rows_are_back_to_the_baseline_single_candidate(self):
        assert PH.V2_SHORT_ROWS[("hold.deep.dividend_cash", PH.CASH_FAILED_NOW)][1:] == (
            PH._v2_raised(PH.SRC_DIV_CASH), PH._V2_NO_EXIT_REPORT)

    def test_the_new_note_has_a_short_row(self):
        card, _f, _b = PH.build_dividend_cash_card(_deep(_cash(failed_tickers=("0056",))))
        short, _full = PH.v2_short_rows(card)
        assert short and all(v for _k, v in short)

    @pytest.mark.parametrize("old,new", [
        ('        reason=MISS_FETCH_FAILED if _cash_failed else "",\n', '        reason="",\n'),
        ("                       and not _cash_failed),\n", "                       ),\n"),
    ])
    def test_c_mutations_turn_red_back_into_grey_or_green(self, old, new):
        m = _mutant(PH, old, new)
        all_failed = m.build_dividend_cash_card(m.DeepReadout(
            requested=True, submitted=True, bound=True, holdings_n=2, has_station_rows=True,
            cash=_cash(gross_twd=0.0, net_after_nhi_twd=0.0, payouts_n=0,
                       failed_tickers=("0056",))))[0]
        partial = m.build_dividend_cash_card(m.DeepReadout(
            requested=True, submitted=True, bound=True, holdings_n=2, has_station_rows=True,
            cash=_cash(failed_tickers=("0056",))))[0]
        assert (all_failed.state, partial.state) != (UI_FAILED, UI_FAILED)
