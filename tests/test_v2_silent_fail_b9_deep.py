"""Q3：「💼 我的持股」⑥ 深度分析三格 —— 壓力測試 `hold.deep.stress`／VaR `hold.deep.var`／
配息現金流 `hold.deep.dividend_cash` 的「算不出來」，哪些其實是**抓取失敗**。

（客戶 2026-09-26 批次授權「失敗被當成沒結果」的卡；⛔ 不新造文案（K1）；⛔ 不動版面；
L3／L1 一律加性參數，預設＝修前行為。）

根因（逐條，每條都「不猜就分辨得出來」才修）：
  ① **持有列整批抓取失敗**（戰情表 `_detail.error`）—— L3 `priced_rows()`／`_shares_of()`
     靜靜跳過（連 `held_n` 都不計）⇒ 全部失敗時三格都落在灰卡「**這是一個有效的結果**」
     （`*_EMPTY_NOW`，where 還叫人去補張數）；部分失敗時是一個漏了那幾檔、卻**沒講**的 live 數字。
  ② **持有列現價抓不到**（沒有錯誤、`現價` 為 None；客戶裁示「現價抓不到 → 紅」，批次 4）——
     壓測／VaR 的 `priced_rows()` 不收它 ⇒ 同上。⚠️ **配息不受影響**（`_shares_of()` 只看張數，
     沒現價的列照樣進了總額）⇒ 配息卡 ⛔ 不收這一種（收了是假警報）。
  ③ **VaR 取價在 L1 被吞掉的例外** —— L1 `_fetch_etf_price_max` 接住例外、回空 df（並快取）⇒
     L3 把它歸成 `no_price`「這檔沒有那段歷史」⇒ 灰卡「若是新上市……等歷史累積」（錯的指引）
     或橘卡。修法：L1 在那個空 df 的 `attrs` 掛旗標；`fetch_etf_price(failed=[])` ／
     L3 `get_portfolio_var(strict=True)` 才讀它（預設不讀 = 修前）。
  ④ **VaR 部分取價拋例外** —— 原本只有「全部拋例外」（`upstream_down`）才紅；部分拋例外是
     **綠卡、一個字都沒講**（那幾檔不在 `no_price`，橘卡也不看 `fetch_errors`）。改：任一檔 → 紅。

修法（文字全部沿用既有）：①② 走各卡既有紅卡 `*_FAILED_NOW`，why 與 ⑤⑥ 核心／衛星（Q2）、
⑤ 停利卡**逐字同一套**（L0 `MISS_TEXT` 摘主詞 ＋ `NO_PRICE_WHY`），where 用 `STATION_ERROR_WHERE`；
③④ 走 VaR 既有的例外紅卡（`_deep_note` ＋ `SRC_VAR`，錯誤原文照印）。

每條路徑五件事：(a) 全部失敗 → 紅；(b) 部分失敗 → 紅；(c) 真的沒有 → 與改前 byte-identical；
(d) 既有呼叫端不傳新參數 → 回傳值不變；(e) 突變：拔掉守衛 → (a)/(b) 轉紅燈。

⚠️ 仍分不出來、本批**未修**（見總管回報）：yfinance 只回空、沒拋例外的取價／配息；
壓測 Beta 查不到（L2 `calc_portfolio_stress_test` 內部 `fetch_etf_info` 吞例外 → 以 1.0 估算）；
L3 `_resolve_yf_ticker()` 判後綴時吞掉的例外（壓測／配息用它挑 `.TW`／`.TWO`）。
"""
from __future__ import annotations

import dataclasses
import hashlib
import importlib.util
import inspect
import pathlib
import sys
import types

import pandas as pd
import pytest

import src.compute.etf.etf_calc as EC
import src.data.etf.etf_fetch as F
import src.services.dividend_tax_service as DTS
import src.services.portfolio_deep_service as PDS
from shared.station_specs import MISS_FETCH_FAILED, MISS_NO_INPUT, MISS_TEXT
from shared.ui_state import UI_DEGRADED, UI_EMPTY, UI_FAILED, UI_IDLE, UI_LIVE
from src.ui.views import page_hold as PH

_VALID = "有效的結果"
_DEEP_KEYS = ("hold.deep.stress", "hold.deep.var", "hold.deep.dividend_cash")
_WHOLE = MISS_TEXT[MISS_FETCH_FAILED].removeprefix("這一檔")
_NO_PX = MISS_TEXT[MISS_NO_INPUT].removeprefix("這盞燈").split("，", 1)[0]


def _mutant(mod: types.ModuleType, *pairs: tuple[str, str]) -> types.ModuleType:
    """把 `mod` 的原始碼裡每一組 `old` **恰好一處**換成 `new`，載成一個獨立的新模組。"""
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    for old, new in pairs:
        assert src.count(old) == 1, f"突變點不唯一或已不存在：{old!r}"
        src = src.replace(old, new)
    name = f"_mutant_b9_{mod.__name__.rsplit('.', 1)[-1]}"
    spec = importlib.util.spec_from_loader(name, loader=None)
    m = importlib.util.module_from_spec(spec)
    m.__file__ = mod.__file__
    sys.modules[name] = m
    try:
        exec(compile(src, mod.__file__, "exec"), m.__dict__)
    finally:
        sys.modules.pop(name, None)
    return m


#: 本批 L5 守衛整段中和（＝本批之前的行為）。L3／L1 的加性參數不在這裡 —— 不傳就是修前。
_REVERT = (
    ("_stress_skipped = deep.failed_rows + deep.unpriced_rows", "_stress_skipped = ()"),
    ("_var_skipped = deep.failed_rows + deep.unpriced_rows", "_var_skipped = ()"),
    ("_cash_skipped = () if (deep.cash_error or deep.error) else deep.failed_rows",
     "_cash_skipped = ()"),
    ('if _res is not None and _res.fetch_errors else "")',
     'if _res is not None and _res.upstream_down else "")'),
    ("lambda _r: get_portfolio_var(_r, strict=True)", "get_portfolio_var"),
)

# 與 L3 `build_station_rows` 產出的列同形（只留 ⑥ 讀到的欄位）。
_OK_A = {"代號": "0056", "種類": "ETF", "held": True, "張數": 2.0, "均價": 30.0,
         "現價": 35.0, "市值": 70.0, "_detail": {}}
_OK_B = {"代號": "2330", "種類": "個股", "held": True, "張數": 1.0, "均價": 500.0,
         "現價": 600.0, "市值": 600.0, "_detail": {}}
_ERR = {"代號": "00878", "種類": "ETF", "held": True, "_detail": {"error": "HTTPError 502"}}
_ERR2 = {"代號": "6505", "種類": "個股", "held": True, "_detail": {"error": "HTTPError 502"}}
_NOPX = {"代號": "2454", "種類": "個股", "held": True, "張數": 1.0, "均價": 900.0,
         "現價": None, "市值": None, "_detail": {}}
_NOLOTS = {"代號": "3008", "種類": "個股", "held": True, "張數": None, "均價": None,
           "現價": 150.0, "市值": None, "_detail": {}}
_W_ERR = dict(_ERR2, 代號="2603", held=False)
_W_NOPX = dict(_NOPX, 代號="2609", held=False)


def _ohlcv(n: int = 60) -> pd.DataFrame:
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=n)
    close = [100.0 + ((i * 7) % 11) - 5 for i in range(n)]
    return pd.DataFrame({"Open": close, "High": [c + 1 for c in close],
                         "Low": [c - 1 for c in close], "Close": close,
                         "Volume": [1000] * n}, index=idx)


def _div_recent() -> pd.Series:
    return pd.Series([1.5], index=[pd.Timestamp.today().normalize() - pd.Timedelta(days=30)])


class _FakeYF:
    """真的 L1 `_fetch_etf_price_max` 會打的 `yf.Ticker(t).history(...)` —— 依表回應。

    表內值：DataFrame → 有價；Exception → **拋例外**（L1 接住、回空 df ＋ 旗標）；
    沒有這個鍵 → yfinance 回空（沒拋例外；L1 分不出來，照舊）。
    """

    def __init__(self, table: dict):
        self.table = table

    def Ticker(self, t):  # noqa: N802 — 對齊 yfinance 的介面名
        step = self.table.get(t)

        class _T:
            def history(self, *a, **k):
                if isinstance(step, Exception):
                    raise step
                return pd.DataFrame() if step is None else step.copy()

        return _T()


@pytest.fixture
def world(monkeypatch):
    """⑥ 三支 L3 是真的；網路面換成離線替身。價格走**真的 L1**（只換 `yf`）。"""
    prices: dict = {}
    divs: dict = {}
    monkeypatch.setattr(F, "yf", _FakeYF(prices))
    monkeypatch.setattr(EC, "fetch_etf_info", lambda t: {})       # Beta 查無（揭露，本批不動）
    monkeypatch.setattr(DTS, "holding_currency", lambda t: "TWD")
    monkeypatch.setattr(DTS, "fetch_etf_dividends",
                        lambda t: divs.get(t, pd.Series(dtype=float)))
    F._fetch_etf_price_max.clear()
    yield prices, divs
    F._fetch_etf_price_max.clear()


def _station(P, rows):
    return P.StationReadout(requested=True, submitted=True, bound=True,
                            holdings_n=len(rows), rows=tuple(rows))


def _three(P, st_):
    dp = P.load_deep(st_)
    return P.build_stress_card(dp), P.build_var_card(dp), P.build_dividend_cash_card(dp)


def _by_key(builts):
    return {b[0].key: b for b in builts}


def _assert_red_rows(built, now, why):
    card, _facts, sig = built
    assert card.state == UI_FAILED and card.state != UI_EMPTY
    assert card.note.now == now
    assert _VALID not in card.note.why
    assert card.note.why == why
    assert card.note.where == PH.STATION_ERROR_WHERE
    assert "重跑" not in card.note.why, "失敗結果被快取時，why 不得叫人重跑"
    assert card.value == "" and sig == ""
    html = PH.v2_card_html(*built)
    assert PH._V2_BLANK_LINE_RE.sub("\n", html) == html, "卡面文字含空行（空行守衛）"


_NOW = {"hold.deep.stress": PH.STRESS_FAILED_NOW, "hold.deep.var": PH.VAR_FAILED_NOW,
        "hold.deep.dividend_cash": PH.CASH_FAILED_NOW}


# ══════════════════════════════════════════════════════════════════
# 根因釘住（L3 本批只加了 VaR 的 `strict=`；跳過列的行為 ⛔ 未改）
# ══════════════════════════════════════════════════════════════════
class TestRootCause:
    def test_l3_silently_skips_error_rows_without_counting_them(self):
        assert PDS.priced_rows([_OK_A, _ERR]) == PDS.priced_rows([_OK_A])
        assert PDS._held_n([_OK_A, _ERR]) == 1, "整批失敗的那一檔連持有數都不進 ⇒ 看起來是完整的"
        assert PDS.get_portfolio_stress([_ERR, _ERR2]).reason == PDS.REASON_NO_PRICED_ROWS
        assert PDS.get_dividend_cash_flow([_ERR]).reason == PDS.REASON_NO_LOTS_ROWS

    def test_l3_skips_unpriced_rows_for_stress_and_var_but_not_for_cash(self):
        assert PDS.priced_rows([_NOPX]) == []
        assert PDS._shares_of([_NOPX]) == [{"ticker": "2454.TW", "shares": 1000.0}]

    def test_before_this_batch_all_failed_rows_were_the_grey_valid_result(self, world):
        old = _mutant(PH, *_REVERT)
        for card, _f, _s in _three(old, _station(old, (_ERR, _ERR2))):
            assert card.state == UI_EMPTY and _VALID in card.note.why

    def test_l1_swallows_the_price_exception_into_an_empty_frame(self, world):
        prices, _ = world
        prices["0056.TW"] = ConnectionError("yahoo 429")
        out = F._fetch_etf_price_max("0056.TW")
        assert out.empty and out.attrs[F.PRICE_FETCH_FAILED_ATTR] == "ConnectionError: yahoo 429"


# ══════════════════════════════════════════════════════════════════
# (a) 全部失敗 → 紅
# ══════════════════════════════════════════════════════════════════
class TestAllFailedIsRed:
    def test_a_all_error_rows_turn_all_three_red(self, world):
        for key, built in _by_key(_three(PH, _station(PH, (_ERR, _ERR2)))).items():
            _assert_red_rows(built, _NOW[key], f"00878、6505：{_WHOLE}")

    def test_a_all_unpriced_rows_turn_stress_and_var_red_but_not_cash(self, world):
        by = _by_key(_three(PH, _station(PH, (_NOPX,))))
        for key in ("hold.deep.stress", "hold.deep.var"):
            _assert_red_rows(by[key], _NOW[key], f"2454：{_NO_PX}")
        cash = by["hold.deep.dividend_cash"][0]
        assert cash.state == UI_EMPTY and cash.note.now == PH.CASH_NO_PAYOUT_NOW, (
            "配息不需要現價 —— 沒現價的列照樣進了總額，⛔ 不得升紅")

    def test_a_both_kinds_list_both_sentences_in_order(self, world):
        by = _by_key(_three(PH, _station(PH, (_ERR, _NOPX))))
        for key in ("hold.deep.stress", "hold.deep.var"):
            _assert_red_rows(by[key], _NOW[key], f"00878：{_WHOLE}2454：{_NO_PX}")
        _assert_red_rows(by["hold.deep.dividend_cash"], PH.CASH_FAILED_NOW, f"00878：{_WHOLE}")

    def test_a_var_l1_swallowed_exception_is_red_not_no_history(self, world):
        prices, _ = world
        prices["0056.TW"] = ConnectionError("yahoo 429")
        prices["2330.TW"] = ConnectionError("yahoo 429")
        card = _by_key(_three(PH, _station(PH, (_OK_A, _OK_B))))["hold.deep.var"][0]
        assert card.state == UI_FAILED and card.note.now == PH.VAR_FAILED_NOW
        assert "0056.TW：ConnectionError: yahoo 429" in card.note.why
        assert "2330.TW：ConnectionError: yahoo 429" in card.note.why
        assert "新上市" not in card.note.where and "重跑" not in card.note.why

    def test_a_same_words_as_the_split_cards_on_the_same_page(self, world):
        """同一頁、同一檔、同一條失敗路徑 ⛔ 不給兩種說法（⑤⑥ 核心／衛星 Q2）。"""
        st_ = _station(PH, (_ERR2, _NOPX))
        split = PH.build_allocation_split_card(st_)[0]
        assert split.state == UI_FAILED
        stress, var, _cash = _three(PH, st_)
        assert stress[0].note.why == var[0].note.why == split.note.why

    def test_a_short_rows_pick_the_existing_excerpts(self, world):
        by = _by_key(_three(PH, _station(PH, (_ERR, _NOPX))))
        for key, built in by.items():
            short = dict(PH.v2_short_rows(built[0])[0])
            assert short[PH.V2_WHY_FACT_KEY].startswith("整批抓取失敗 —— 看該列的錯誤訊息")
            assert short[PH.V2_GUIDE_FACT_KEY] == PH._V2_CHECK_NET, key

    def test_a_an_upstream_exception_still_wins_and_keeps_its_note(self, world):
        dp = PH.DeepReadout(requested=True, submitted=True, bound=True, holdings_n=1,
                            has_station_rows=True, failed_rows=("00878",),
                            stress_error="RuntimeError('x')", var_error="RuntimeError('x')",
                            cash_error="RuntimeError('x')")
        for fn, now, src in ((PH.build_stress_card, PH.STRESS_FAILED_NOW, PH.SRC_STRESS),
                             (PH.build_var_card, PH.VAR_FAILED_NOW, PH.SRC_VAR),
                             (PH.build_dividend_cash_card, PH.CASH_FAILED_NOW, PH.SRC_DIV_CASH)):
            card = fn(dp)[0]
            assert card.note == PH._deep_note(dp, now=now, source=src, error="RuntimeError('x')")


# ══════════════════════════════════════════════════════════════════
# (b) 部分失敗 → 紅（⛔ 不畫那個漏了幾檔的數字）
# ══════════════════════════════════════════════════════════════════
class TestPartialFailureIsRed:
    def test_b_one_error_row_beside_a_good_one(self, world):
        prices, divs = world
        prices["0056.TW"] = _ohlcv()
        divs["0056.TW"] = _div_recent()
        st_ = _station(PH, (_OK_A, _ERR))
        old = _by_key(_three(_mutant(PH, *_REVERT), st_))
        for key in _DEEP_KEYS:
            assert old[key][0].state == UI_LIVE, f"前提：修前 {key} 是 live（漏了 00878 卻沒講）"
        for key, built in _by_key(_three(PH, st_)).items():
            _assert_red_rows(built, _NOW[key], f"00878：{_WHOLE}")
            assert not any(k.startswith("現值") for k, _ in built[1])

    def test_b_one_unpriced_row_turns_stress_and_var_red_cash_stays_live(self, world):
        prices, divs = world
        prices["0056.TW"] = _ohlcv()
        divs["0056.TW"] = _div_recent()
        by = _by_key(_three(PH, _station(PH, (_OK_A, _NOPX))))
        for key in ("hold.deep.stress", "hold.deep.var"):
            _assert_red_rows(by[key], _NOW[key], f"2454：{_NO_PX}")
        assert by["hold.deep.dividend_cash"][0].state == UI_LIVE

    def test_b_var_partial_l1_swallowed_exception_is_red_not_orange(self, world):
        prices, _ = world
        prices["0056.TW"] = _ohlcv()
        prices["2330.TW"] = ConnectionError("yahoo 429")
        st_ = _station(PH, (_OK_A, _OK_B))
        old = _by_key(_three(_mutant(PH, *_REVERT), st_))["hold.deep.var"][0]
        assert old.state == UI_DEGRADED, "前提：修前它被當成「抓不到價格序列」（新上市？）的橘卡"
        card = _by_key(_three(PH, st_))["hold.deep.var"][0]
        assert card.state == UI_FAILED and card.note.now == PH.VAR_FAILED_NOW
        assert "2330.TW：ConnectionError: yahoo 429" in card.note.why

    def test_b_var_partial_raised_exception_is_red_not_a_silent_live(self):
        res = PDS.VarResult(computed=True, hist_95_twd=1.0, hist_99_twd=2.0,
                            monthly_99_twd=3.0, monthly_99_pct=1.0, covered_value_twd=10.0,
                            total_value_twd=10.0, coverage_pct=100.0, n_common=40,
                            valued_n=2, held_n=2, tickers_used=("0056.TW",),
                            fetch_errors=("2330.TW：RuntimeError: boom",))
        dp = PH.DeepReadout(requested=True, submitted=True, bound=True, holdings_n=2,
                            has_station_rows=True, var=res)
        old = _mutant(PH, *_REVERT)
        assert old.build_var_card(old.DeepReadout(**dp.__dict__))[0].state == UI_LIVE, (
            "前提：修前部分拋例外是綠卡，而且卡上沒有任何一處提到 2330")
        card = PH.build_var_card(dp)[0]
        assert card.state == UI_FAILED and "2330.TW：RuntimeError: boom" in card.note.why


# ══════════════════════════════════════════════════════════════════
# (c) 真的沒有 → 與改前 byte-identical
# ══════════════════════════════════════════════════════════════════
def _fp(P, built) -> str:
    card, facts, sig = built
    return repr((card, tuple(facts), sig)) + P.v2_card_html(card, facts, sig)


def _genuine(P, world):
    """沒有任何「取數失敗」的輸入（含 yfinance 只回空、沒拋例外）—— 本批 ⛔ 不得改動。"""
    prices, divs = world
    prices.clear()
    divs.clear()
    F._fetch_etf_price_max.clear()
    prices["0056.TW"] = _ohlcv()
    prices["2330.TW"] = _ohlcv()
    prices["00919.TW"] = _ohlcv(10)                 # 樣本不足一個月（真的太短）
    divs["0056.TW"] = _div_recent()
    out = []
    for rows in (
            (_NOLOTS,),                              # 有現價、缺張數 → 缺輸入
            (_W_ERR, _W_NOPX),                       # 只有觀察清單（抓不到也不進 ⑥）
            (_OK_A, _OK_B),                          # 全部正常
            (_OK_A, _NOLOTS),                        # 部分缺張數 → live ＋ 涵蓋範圍
            (dict(_OK_A, 代號="00919"),),             # VaR 樣本太短 → 灰
            (_OK_A, dict(_OK_B, 代號="1101")),        # 1101 yfinance 回空（沒拋例外）→ 橘 no_price
            (dict(_OK_B, 代號="1101"),),              # 全部回空（沒拋例外）→ 灰
            (_OK_B,),                                # 配息近一年 0 筆 → 灰 NO_PAYOUT
    ):
        out.extend(_three(P, _station(P, rows)))
    for st_ in (P.StationReadout(requested=True, submitted=True, bound=True),
                P.StationReadout(requested=True, submitted=True, bound=True, holdings_n=2,
                                 rows=(_ERR,), error="RuntimeError('boom')"),
                P.StationReadout(requested=False, submitted=True),
                P.StationReadout(requested=False, submitted=False)):
        out.extend(_three(P, st_))
    return out


class TestGenuineEmptyUnchanged:
    def test_c_missing_lots_stays_the_grey_valid_result(self, world):
        by = _by_key(_three(PH, _station(PH, (_NOLOTS,))))
        for key, now in (("hold.deep.stress", PH.STRESS_EMPTY_NOW),
                         ("hold.deep.var", PH.VAR_EMPTY_NOW),
                         ("hold.deep.dividend_cash", PH.CASH_EMPTY_NOW)):
            assert by[key][0].state == UI_EMPTY and by[key][0].note.now == now
            assert _VALID in by[key][0].note.why

    def test_c_watchlist_failures_do_not_touch_the_deep_cards(self, world):
        for card, _f, _s in _three(PH, _station(PH, (_W_ERR, _W_NOPX))):
            assert card.state == UI_EMPTY and _VALID in card.note.why

    def test_c_yfinance_empty_without_exception_is_still_no_history(self, world):
        by = _by_key(_three(PH, _station(PH, (dict(_OK_B, 代號="1101"),))))
        var = by["hold.deep.var"][0]
        assert var.state == UI_EMPTY and var.note.now == PH.VAR_EMPTY_NOW

    def test_c_every_genuine_input_is_byte_identical_to_before(self, world):
        old = _mutant(PH, *_REVERT)
        before = [_fp(old, b) for b in _genuine(old, world)]
        after = [_fp(PH, b) for b in _genuine(PH, world)]
        assert len(before) == len(after) == 3 * 12
        assert {b[0].state for b in _genuine(PH, world)} >= {
            UI_LIVE, UI_EMPTY, UI_DEGRADED, UI_FAILED, UI_IDLE}, "窮舉沒走到該走的態"
        assert before == after


# ══════════════════════════════════════════════════════════════════
# (d) 既有呼叫端 —— 不傳新參數，回傳值不變
# ══════════════════════════════════════════════════════════════════
class TestExistingCallersUnchanged:
    def test_d_signatures_only_gained_keyword_only_defaults(self):
        p = inspect.signature(F.fetch_etf_price).parameters
        assert list(p) == ["ticker", "period", "failed"]
        assert p["failed"].kind is inspect.Parameter.KEYWORD_ONLY and p["failed"].default is None
        p = inspect.signature(PDS.get_portfolio_var).parameters
        assert list(p) == ["rows", "strict"]
        assert p["strict"].kind is inspect.Parameter.KEYWORD_ONLY and p["strict"].default is False
        assert list(inspect.signature(PDS.get_portfolio_stress).parameters) == ["rows", "drop_pct"]
        assert list(inspect.signature(PDS.get_dividend_cash_flow).parameters) == ["rows"]

    def test_d_l1_without_failed_returns_the_same_clean_empty_frame(self, world):
        prices, _ = world
        prices["0056.TW"] = ConnectionError("boom")
        out = F.fetch_etf_price("0056.TW", period="1y")
        assert isinstance(out, pd.DataFrame) and out.empty and out.attrs == {}, (
            "不傳 `failed=` 的呼叫端拿到的必須跟修前一樣（attrs 為空的空 df）")
        got: list = []
        out2 = F.fetch_etf_price("0056.TW", period="1y", failed=got)
        assert out2.empty and out2.attrs == {} and got == ["ConnectionError: boom"]

    def test_d_l1_empty_without_exception_and_data_are_untouched(self, world):
        prices, _ = world
        prices["0050.TW"] = _ohlcv()
        got: list = []
        assert F.fetch_etf_price("9999.TW", period="1y", failed=got).empty and got == []
        a = F.fetch_etf_price("0050.TW", period="1y")
        b = F.fetch_etf_price("0050.TW", period="1y", failed=got)
        assert got == [] and a.equals(b) and a.attrs == b.attrs

    def test_d_l3_var_without_strict_is_the_pre_batch_no_price(self, world):
        prices, _ = world
        prices["0056.TW"] = ConnectionError("yahoo 429")
        prices["2330.TW"] = ConnectionError("yahoo 429")
        res = PDS.get_portfolio_var([_OK_A, _OK_B])
        assert res.reason == PDS.REASON_NO_RETURNS
        assert res.no_price == ("0056.TW", "2330.TW") and res.fetch_errors == ()
        strict = PDS.get_portfolio_var([_OK_A, _OK_B], strict=True)
        assert strict.no_price == () and len(strict.fetch_errors) == 2
        # 其餘欄位一律相同（只是從一組搬到另一組）。
        _d, _s = dataclasses.asdict(res), dataclasses.asdict(strict)
        for k in ("no_price", "fetch_errors"):
            _d.pop(k), _s.pop(k)
        assert _d == _s

    def test_d_l3_var_without_strict_equals_a_build_without_the_strict_code(self, world):
        prices, _ = world
        prices["0056.TW"] = _ohlcv()
        prices["2330.TW"] = ConnectionError("yahoo 429")
        old = _mutant(PDS, ("    _rets, _missing, _errors = (_daily_returns(list(_w), strict=True)"
                            " if strict\n                                else _daily_returns("
                            "list(_w)))\n", "    _rets, _missing, _errors = _daily_returns(list(_w))\n"))
        for rows in ([_OK_A, _OK_B], [_OK_A], [_ERR, _NOPX], [_NOLOTS]):
            assert (dataclasses.asdict(PDS.get_portfolio_var(rows))
                    == dataclasses.asdict(old.get_portfolio_var(rows))), rows

    def test_d_every_other_hold_card_is_byte_identical_with_or_without_this_batch(self):
        from tests import test_p04_hold_v2_cards as E

        def _prints(P):
            _orig = E.P
            E.P = P
            try:
                _notes, builts = E._enumerate()
            finally:
                E.P = _orig
            out = []
            for card, facts, sig in builts:
                _k = repr((card, tuple(facts), sig)) + P.v2_card_html(card, facts, sig)
                _new = (card.key in _DEEP_KEYS and card.state == UI_FAILED
                        and card.note.where == P.STATION_ERROR_WHERE)
                out.append((card.key, card.state, _new,
                            hashlib.sha256(_k.encode()).hexdigest()))
            return out

        before = _prints(_mutant(PH, *_REVERT))
        after = _prints(PH)
        assert len(before) == len(after) > 1000
        new_idx = {i for i, a in enumerate(after) if a[2]}
        # 窮舉裡本批那三例 × 壓測／VaR ＋ 配息兩例（「只有現價抓不到」配息照舊 live）。
        assert len(new_idx) == 8
        assert not any(b[2] for b in before)
        assert all(before[i][1] != UI_FAILED for i in new_idx)
        assert ([b for i, b in enumerate(before) if i not in new_idx]
                == [a for i, a in enumerate(after) if i not in new_idx]), "有既有卡的輸出變了"


# ══════════════════════════════════════════════════════════════════
# N1（總管裁定，只刪不加）：①② 觸發的紅卡不出「涵蓋範圍」（及配息的同類列）
# ══════════════════════════════════════════════════════════════════
_COVER = "涵蓋範圍"
_CASH_PART = "⚠️ 這個總額只涵蓋一部分持股"


def _labels(built) -> list[str]:
    return [k for k, _v in built[1]]


def _cash_res(**kw) -> PDS.DividendCashResult:
    base = dict(computed=True, gross_twd=30000.0, net_after_nhi_twd=30000.0, payouts_n=8,
                tw_n=1, lots_n=1, held_n=2, shares_total=1000.0, coverage_pct=50.0,
                excluded_tickers=("00919.TW",))
    return PDS.DividendCashResult(**{**base, **kw})


class TestN1CoverageRowNotOnRowFailureRed:
    def test_n1_stress_and_var_error_row_red_has_no_coverage_row(self, world):
        prices, divs = world
        prices["0056.TW"] = _ohlcv()
        st_ = _station(PH, (_OK_A, _ERR))
        old = _by_key(_three(_mutant(PH, ("coverage=not _stress_skipped", "coverage=True"),
                                         ("coverage=not _var_skipped", "coverage=True")), st_))
        for key in ("hold.deep.stress", "hold.deep.var"):
            # 前提：修前那一列寫「1 檔持有列裡納入了 1 檔」—— why 卻在說 00878 整批失敗。
            assert dict(old[key][1])[_COVER] == "1 檔持有列裡納入了 1 檔", key
        for key, built in _by_key(_three(PH, st_)).items():
            assert built[0].state == UI_FAILED
            assert _COVER not in _labels(built), key
            assert "納入了" not in PH.v2_card_html(*built), key

    def test_n1_stress_and_var_no_price_red_has_no_coverage_row(self, world):
        prices, divs = world
        prices["0056.TW"] = _ohlcv()
        divs["0056.TW"] = _div_recent()
        by = _by_key(_three(PH, _station(PH, (_OK_A, _NOPX))))
        for key in ("hold.deep.stress", "hold.deep.var"):
            assert by[key][0].state == UI_FAILED and _COVER not in _labels(by[key]), key
        # 配息不收「現價抓不到」→ 照舊 live，「涵蓋範圍」照舊（2 檔裡納入 2 檔 → 不出列是既有行為）。
        assert by["hold.deep.dividend_cash"][0].state == UI_LIVE

    def test_n1_other_fact_rows_on_the_red_card_are_untouched(self, world):
        prices, _ = world
        prices["0056.TW"] = _ohlcv()
        st_ = _station(PH, (_OK_A, _ERR))
        old = _by_key(_three(_mutant(PH, ("coverage=not _stress_skipped", "coverage=True"),
                                         ("coverage=not _var_skipped", "coverage=True")), st_))
        new = _by_key(_three(PH, st_))
        for key in ("hold.deep.stress", "hold.deep.var"):
            assert [f for f in old[key][1] if f[0] != _COVER] == list(new[key][1]), (
                f"{key}：只准少「涵蓋範圍」那一列，其餘 facts 逐列不變（只刪不加）")

    def test_n1_existing_var_exception_red_keeps_the_coverage_row(self, world):
        """③④ 觸發、沒有持有列失敗的既有紅態 → 照舊出（總管：既有紅態維持原樣）。"""
        prices, _ = world
        prices["0056.TW"] = _ohlcv()
        prices["2330.TW"] = ConnectionError("yahoo 429")
        var = _by_key(_three(PH, _station(PH, (_OK_A, _OK_B))))["hold.deep.var"]
        assert var[0].state == UI_FAILED
        assert dict(var[1])[_COVER] == "2 檔持有列裡納入了 2 檔"
        prices["0056.TW"] = ConnectionError("yahoo 429")         # upstream_down
        F._fetch_etf_price_max.clear()
        var = _by_key(_three(PH, _station(PH, (_OK_A, _OK_B))))["hold.deep.var"]
        assert var[0].state == UI_FAILED and dict(var[1])[_COVER] == "2 檔持有列裡納入了 2 檔"

    def test_n1_cash_row_failure_red_drops_both_same_kind_rows(self):
        dp = PH.DeepReadout(requested=True, submitted=True, bound=True, holdings_n=3,
                            has_station_rows=True, cash=_cash_res(), failed_rows=("00878",))
        built = PH.build_dividend_cash_card(dp)
        assert built[0].state == UI_FAILED and built[0].note.where == PH.STATION_ERROR_WHERE
        assert _COVER not in _labels(built) and _CASH_PART not in _labels(built)
        old = _mutant(PH, ("and _lots < _held and not _cash_skipped:", "and _lots < _held:"),
                      ("if _degraded and not _cash_skipped:", "if _degraded:"))
        before = old.build_dividend_cash_card(old.DeepReadout(**dp.__dict__))
        assert dict(before[1])[_COVER].startswith("2 檔持有列裡納入了 1 檔")
        assert dict(before[1])[_CASH_PART].startswith("覆蓋率 50.0%")
        assert [f for f in before[1] if f[0] not in (_COVER, _CASH_PART)] == list(built[1])

    def test_n1_cash_existing_l1_failure_red_keeps_both_rows(self):
        """批次 3 的既有紅態（L1 配息抓取失敗、沒有持有列失敗）→ 照舊出。"""
        dp = PH.DeepReadout(requested=True, submitted=True, bound=True, holdings_n=2,
                            has_station_rows=True,
                            cash=_cash_res(failed_tickers=("0056.TW",),
                                           failed_detail=("0056.TW: RuntimeError: x",)))
        built = PH.build_dividend_cash_card(dp)
        assert built[0].state == UI_FAILED and built[0].note.where != PH.STATION_ERROR_WHERE
        assert _COVER in _labels(built) and _CASH_PART in _labels(built)

    def test_n1_cash_non_red_still_shows_both_rows(self):
        built = PH.build_dividend_cash_card(PH.DeepReadout(
            requested=True, submitted=True, bound=True, holdings_n=2, has_station_rows=True,
            cash=_cash_res()))
        assert built[0].state == UI_DEGRADED
        assert _COVER in _labels(built) and _CASH_PART in _labels(built)


# ══════════════════════════════════════════════════════════════════
# N5：`.TW`／`.TWO` 兩段式取價的兩個方向 ＋ 新 log 行
# ══════════════════════════════════════════════════════════════════
class TestN5OtcFallbackAndLog:
    def test_n5_tw_exception_but_two_ok_is_success_not_red(self, world):
        prices, _ = world
        prices["0056.TW"] = ConnectionError("yahoo 429")
        prices["0056.TWO"] = _ohlcv()
        res = PDS.get_portfolio_var([_OK_A], strict=True)
        assert res.fetch_errors == () and res.no_price == ()
        assert res.computed and res.tickers_used == ("0056.TW",)
        card = _by_key(_three(PH, _station(PH, (_OK_A,))))["hold.deep.var"][0]
        assert card.state == UI_LIVE, "`.TWO` 抓到資料 ＝ 這一檔就是上櫃，不是取價失敗"

    def test_n5_tw_empty_but_two_exception_is_red(self, world):
        prices, _ = world
        prices["0056.TWO"] = ConnectionError("yahoo 429")          # `.TW` 回空（沒拋例外）
        res = PDS.get_portfolio_var([_OK_A], strict=True)
        assert res.fetch_errors == ("0056.TW：ConnectionError: yahoo 429",)
        assert res.no_price == ()
        card = _by_key(_three(PH, _station(PH, (_OK_A,))))["hold.deep.var"][0]
        assert card.state == UI_FAILED and card.note.now == PH.VAR_FAILED_NOW
        assert "0056.TW：ConnectionError: yahoo 429" in card.note.why

    def test_n5_the_strict_failure_is_logged(self, world, capsys):
        prices, _ = world
        prices["0056.TW"] = ConnectionError("yahoo 429")
        PDS.get_portfolio_var([_OK_A], strict=True)
        out = capsys.readouterr().out
        assert ("[portfolio_deep/var] 0056.TW 價格抓取失敗（L1 已接住）："
                "ConnectionError: yahoo 429\n") in out
        # 快取命中那一次 L1 不會再印 —— 那時只剩 L3 這一行在說話。
        PDS.get_portfolio_var([_OK_A], strict=True)
        out2 = capsys.readouterr().out
        assert "[etf_fetch]" not in out2 and "（L1 已接住）：ConnectionError: yahoo 429" in out2

    def test_n5_without_strict_the_new_line_is_not_printed(self, world, capsys):
        prices, _ = world
        prices["0056.TW"] = ConnectionError("yahoo 429")
        PDS.get_portfolio_var([_OK_A])
        assert "L1 已接住" not in capsys.readouterr().out


# ══════════════════════════════════════════════════════════════════
# 合併前（總管裁定，只刪不加）：紅卡不出「⚠️ 兩套算法對不起來…判『已失準』（橘）」
# ══════════════════════════════════════════════════════════════════
_RECON = "⚠️ 兩套算法對不起來"
#: 修前（`_valued_facts` 不看卡片狀態）＝ 把那一道判定拿掉。
_RECON_REVERT = ('    if not red and getattr(result, "reconciled", True) is False:',
                 '    if getattr(result, "reconciled", True) is False:')


@pytest.fixture
def unreconciled(monkeypatch):
    """替身：L3 §4.3 對帳一律對不上（`reconciled=False`）—— 其餘全走真的 L3。"""
    monkeypatch.setattr(PDS, "_reconcile", lambda rows, mine: (False, 1.0))


class TestReconcileRowNotOnRed:
    def test_row_failure_red_has_no_reconcile_row(self, world, unreconciled):
        """① 觸發的紅（整批失敗列）。"""
        prices, _ = world
        prices["0056.TW"] = _ohlcv()
        st_ = _station(PH, (_OK_A, _ERR))
        old = _by_key(_three(_mutant(PH, _RECON_REVERT), st_))
        new = _by_key(_three(PH, st_))
        for key in ("hold.deep.stress", "hold.deep.var"):
            assert _RECON in _labels(old[key]), f"前提：修前 {key} 紅卡上掛著「判已失準（橘）」"
            assert new[key][0].state == UI_FAILED and _RECON not in _labels(new[key]), key
            assert "（橘）" not in PH.v2_card_html(*new[key]), key
            assert [f for f in old[key][1] if f[0] != _RECON] == list(new[key][1]), (
                f"{key}：只准少那一列（只刪不加）")

    def test_no_price_red_has_no_reconcile_row(self, world, unreconciled):
        """② 觸發的紅（現價抓不到）。"""
        prices, _ = world
        prices["0056.TW"] = _ohlcv()
        by = _by_key(_three(PH, _station(PH, (_OK_A, _NOPX))))
        for key in ("hold.deep.stress", "hold.deep.var"):
            assert by[key][0].state == UI_FAILED and _RECON not in _labels(by[key]), key

    def test_l1_swallowed_exception_red_has_no_reconcile_row(self, world, unreconciled):
        """③ 觸發的紅（L1 吞掉的取價例外，部分失敗 → 不是 `upstream_down`）。"""
        prices, _ = world
        prices["0056.TW"] = _ohlcv()
        prices["2330.TW"] = ConnectionError("yahoo 429")
        st_ = _station(PH, (_OK_A, _OK_B))
        assert PH.load_deep(st_).var.upstream_down is False
        old = _by_key(_three(_mutant(PH, _RECON_REVERT), st_))["hold.deep.var"]
        var = _by_key(_three(PH, st_))["hold.deep.var"]
        assert _RECON in _labels(old), "前提：修前這張紅卡上掛著「判已失準（橘）」"
        assert var[0].state == UI_FAILED and _RECON not in _labels(var)
        assert _COVER in _labels(var), "「涵蓋範圍」在 ③ 的紅態照舊出（N1 只管 ①②）"

    def test_upstream_down_red_has_no_reconcile_row(self, world, unreconciled):
        """既有的 `upstream_down` 紅卡（一檔都沒抓成）—— 那張寫「橘」本來就不實。"""
        prices, _ = world
        prices["0056.TW"] = ConnectionError("yahoo 429")
        prices["2330.TW"] = ConnectionError("yahoo 429")
        st_ = _station(PH, (_OK_A, _OK_B))
        assert PH.load_deep(st_).var.upstream_down is True
        old = _by_key(_three(_mutant(PH, _RECON_REVERT), st_))["hold.deep.var"]
        var = _by_key(_three(PH, st_))["hold.deep.var"]
        assert old[0].state == UI_FAILED and _RECON in _labels(old)
        assert var[0].state == UI_FAILED and _RECON not in _labels(var)
        # 本批之前就有的那條路徑（非 strict、例外往上拋）也一樣。
        res = PDS.VarResult(reason=PDS.REASON_NO_RETURNS, total_value_twd=10.0, valued_n=1,
                            held_n=1, reconciled=False, reference_value_twd=1.0,
                            fetch_errors=("0056.TW：RuntimeError: boom",))
        assert res.upstream_down is True
        built = PH.build_var_card(PH.DeepReadout(requested=True, submitted=True, bound=True,
                                                 holdings_n=1, has_station_rows=True, var=res))
        assert built[0].state == UI_FAILED and _RECON not in _labels(built)

    def test_orange_card_still_shows_the_reconcile_row(self, world, unreconciled):
        """非紅（橘）照舊：那一列正是橘卡的理由之一。"""
        prices, _ = world
        prices["0056.TW"] = _ohlcv()
        by = _by_key(_three(PH, _station(PH, (_OK_A,))))
        old = _by_key(_three(_mutant(PH, _RECON_REVERT), _station(PH, (_OK_A,))))
        for key in ("hold.deep.stress", "hold.deep.var"):
            assert by[key][0].state == UI_DEGRADED, key
            assert _RECON in _labels(by[key]), key
            assert _fp(PH, by[key]) == _fp(PH, old[key]), f"{key}：橘卡必須與修前逐位元組相同"

    def test_the_explaining_sentence_is_unchanged_where_it_still_shows(self):
        res = PDS.StressResult(computed=True, total_value_twd=100.0, reconciled=False,
                               reference_value_twd=50.0, valued_n=1, held_n=1)
        assert dict(PH._valued_facts(res))[_RECON].endswith(
            "**這一格因此判「已失準」（橘），不是「運作中」（綠）**")
        assert _RECON not in dict(PH._valued_facts(res, red=True))
        assert "涵蓋範圍" in dict(PH._valued_facts(res, red=True)), "red 只管那一列"


# ══════════════════════════════════════════════════════════════════
# 套上 Q4（`load_holdings` 改用 `get_holdings(keep_blank=True)`）之後的確認：
# 「缺張數／均價、但有現價」的持有列 ⛔ 不得被 ①② 判成紅（Q2 規格：缺輸入不是取數失敗）
# ══════════════════════════════════════════════════════════════════
def _sheet_rec(ticker, lots, avg):
    return {"name": "核心", "ticker": ticker, "lots": lots, "avg_price": avg,
            "updated_at": "2026-09-26 09:00:00"}


def _station_metrics(tk, ak):
    idx = pd.date_range("2020-01-03", periods=300, freq="W-FRI")
    if ak == "etf":
        return {"weekly_close": pd.Series([30 + (i % 7) * 0.3 for i in range(300)], index=idx),
                "current_price": 35.0}
    return {"mj_grade": "A", "mj_score_pct": 80, "mj_headline": "ok", "mj_fail_items": [],
            "kd_state": {"k": 50, "d": 40, "label": "中性"}, "name": tk,
            "trend_verdict": None, "current_price": 125.0}


@pytest.fixture
def q4_sheet(monkeypatch, world):
    """真的 L1 `load_portfolio` 解析 → 真的 L3 `get_holdings(keep_blank=True)` → 真的戰情表列
    → 真的 ⑥ 三支 L3。只換掉「讀 Google」與逐檔 metrics 兩步（同 `test_v2_silent_fail_b10_sheet`）。"""
    import src.data.portfolio.gsheet_portfolio as GSP
    import src.services.dividend_station_service as S
    from shared import dividend_station_thresholds as T

    assert T.KIND_ETF == "etf"
    monkeypatch.setattr(S, "resolve_holding_names", lambda h: h)
    monkeypatch.setattr(S, "get_station_rows", lambda hold: (
        S.build_station_rows(hold, vix=18.0, metrics_fn=_station_metrics), 18.0))
    GSP.clear_read_cache()

    def _use(records):
        def _all_records(*, sheet_id=None, worksheet_name=GSP._WORKSHEET_NAME, headers=None):
            return [dict(r) for r in records] if worksheet_name == GSP._WORKSHEET_NAME else []
        monkeypatch.setattr(GSP, "_all_records", _all_records)
        monkeypatch.setattr(GSP, "_has_oauth_tokens", lambda: True)
        monkeypatch.setattr(GSP, "_get_active_sheet_id", lambda: "SHEET1")
        monkeypatch.setattr(GSP, "_get_active_stock_sheet_id", lambda: "")
        monkeypatch.setattr(GSP, "_oauth_import_error", lambda: "")
        GSP.clear_read_cache()
        st_ = PH.load_station(PH.load_holdings(PH.HoldRequest(
            submitted=True, mode=PH.SCOPE_WITH_BINDING)))
        return st_, PH.load_deep(st_)
    yield _use
    GSP.clear_read_cache()


class TestQ4BlankCellsAreNotRowFailures:
    def test_q4_all_blank_lots_or_avg_are_grey_not_red(self, q4_sheet):
        st_, dp = q4_sheet((_sheet_rec("0056", "", ""), _sheet_rec("2330", 3, ""),
                            _sheet_rec("00878", "", 18.5)))
        assert not st_.error and len(st_.rows) == 3
        assert {r["代號"]: (r["張數"], r["現價"]) for r in st_.rows} == {
            "0056": (None, 35.0), "2330": (3.0, 125.0), "00878": (None, 35.0)}, (
            "前提：Q4 的缺值列進得來、而且有現價")
        assert (dp.failed_rows, dp.unpriced_rows) == ((), ()), "缺張數但有現價被當成取數失敗"
        for card, _f, _s in (PH.build_stress_card(dp), PH.build_var_card(dp),
                             PH.build_dividend_cash_card(dp)):
            assert card.state != UI_FAILED, card.key
            assert card.state == UI_EMPTY and _VALID in card.note.why, card.key

    def test_q4_one_blank_row_beside_a_valid_one_is_not_red(self, q4_sheet, world):
        prices, divs = world
        prices["0056.TW"] = _ohlcv()
        divs["0056.TW"] = _div_recent()
        st_, dp = q4_sheet((_sheet_rec("0056", 3, 30.0), _sheet_rec("2330", "", "")))
        assert (dp.failed_rows, dp.unpriced_rows) == ((), ())
        for card, _f, _s in (PH.build_stress_card(dp), PH.build_var_card(dp),
                             PH.build_dividend_cash_card(dp)):
            assert card.state in (UI_LIVE, UI_DEGRADED), (card.key, card.state)

    def test_q4_a_blank_row_whose_price_really_failed_is_still_red(self, q4_sheet, monkeypatch):
        """反證：同一條 Q4 路徑上，**現價真的抓不到**的那一列照舊判 ②（紅）—— 上面兩條不是因為判定被關掉才綠。"""
        import src.services.dividend_station_service as S

        def _no_price(tk, ak):
            m = _station_metrics(tk, ak)
            return {**m, "current_price": None} if ak != "etf" else m
        monkeypatch.setattr(S, "get_station_rows", lambda hold: (
            S.build_station_rows(hold, vix=18.0, metrics_fn=_no_price), 18.0))
        _st, dp = q4_sheet((_sheet_rec("2330", "", ""),))
        assert dp.unpriced_rows == ("2330",)
        assert PH.build_stress_card(dp)[0].state == UI_FAILED


# ══════════════════════════════════════════════════════════════════
# (e) 突變 —— 拔掉本批守衛，(a)/(b) 必須轉紅燈
# ══════════════════════════════════════════════════════════════════
class TestMutations:
    @pytest.mark.parametrize("i,key", [(0, "hold.deep.stress"), (1, "hold.deep.var"),
                                       (2, "hold.deep.dividend_cash")])
    def test_e_dropping_each_row_guard_turns_all_failed_back_into_a_valid_empty(
            self, world, i, key):
        m = _mutant(PH, _REVERT[i])
        card = _by_key(_three(m, _station(m, (_ERR, _ERR2))))[key][0]
        assert card.state == UI_EMPTY and _VALID in card.note.why

    @pytest.mark.parametrize("old,new,key", [
        ("has_value=bool(_res is not None and _res.computed and not _stress_skipped),",
         "has_value=bool(_res is not None and _res.computed),", "hold.deep.stress"),
        ("has_value=bool(_res is not None and _res.computed and not _var_skipped),",
         "has_value=bool(_res is not None and _res.computed),", "hold.deep.var"),
        ("                       and not _cash_failed),\n", "                       ),\n",
         "hold.deep.dividend_cash"),
    ])
    def test_e_dropping_the_partial_guard_turns_partial_live(self, world, old, new, key):
        prices, divs = world
        prices["0056.TW"] = _ohlcv()
        divs["0056.TW"] = _div_recent()
        m = _mutant(PH, (old, new))
        assert _by_key(_three(m, _station(m, (_OK_A, _ERR))))[key][0].state == UI_LIVE

    def test_e_back_to_upstream_down_only_turns_partial_exceptions_green(self):
        m = _mutant(PH, _REVERT[3])
        res = PDS.VarResult(computed=True, covered_value_twd=10.0, total_value_twd=10.0,
                            coverage_pct=100.0, n_common=40, valued_n=2, held_n=2,
                            tickers_used=("0056.TW",), fetch_errors=("2330.TW：E: x",))
        assert m.build_var_card(m.DeepReadout(
            requested=True, submitted=True, bound=True, holdings_n=2, has_station_rows=True,
            var=res))[0].state == UI_LIVE

    def test_e_page_not_asking_for_strict_turns_the_l1_failure_grey(self, world):
        prices, _ = world
        prices["0056.TW"] = ConnectionError("yahoo 429")
        prices["2330.TW"] = ConnectionError("yahoo 429")
        m = _mutant(PH, _REVERT[4])
        card = _by_key(_three(m, _station(m, (_OK_A, _OK_B))))["hold.deep.var"][0]
        assert card.state == UI_EMPTY and card.note.now == PH.VAR_EMPTY_NOW

    def test_e_l3_ignoring_the_l1_flag_turns_it_back_into_no_price(self, world):
        prices, _ = world
        prices["0056.TW"] = ConnectionError("yahoo 429")
        m = _mutant(PDS, ("        if _df is None and _l1_failed:\n", "        if False:\n"))
        res = m.get_portfolio_var([_OK_A], strict=True)
        assert res.fetch_errors == () and res.no_price == ("0056.TW",)

    def test_e_l1_not_flagging_the_exception_is_caught(self, monkeypatch):
        m = _mutant(F, ("        _empty.attrs[PRICE_FETCH_FAILED_ATTR] = f'{type(e).__name__}: {e}'\n",
                        ""))
        monkeypatch.setattr(m, "yf", _FakeYF({"0056.TW": ConnectionError("x")}))
        m._fetch_etf_price_max.clear()
        got: list = []
        assert m.fetch_etf_price("0056.TW", period="1y", failed=got).empty
        assert got == [], "拿掉旗標後 `failed=` 必須收不到東西 —— 否則 (a) 的 L1 那一條沒守到"
        m._fetch_etf_price_max.clear()

    def test_e_counting_unpriced_rows_for_cash_is_caught_by_c(self, world):
        prices, divs = world
        prices["0056.TW"] = _ohlcv()
        divs["0056.TW"] = _div_recent()
        m = _mutant(PH, ("else deep.failed_rows\n",
                         "else deep.failed_rows + deep.unpriced_rows\n"))
        cash = _by_key(_three(m, _station(m, (_OK_A, _NOPX))))["hold.deep.dividend_cash"][0]
        assert cash.state == UI_FAILED, "配息沒用到現價 —— 這一條突變必須被 (b) 的 live 斷言抓到"

    # ── N1 的突變（只刪不加的那幾刀退回去 → 紅卡上又出現「涵蓋範圍」）────────────
    @pytest.mark.parametrize("old,new,key", [
        ("coverage=not _stress_skipped", "coverage=True", "hold.deep.stress"),
        ("coverage=not _var_skipped", "coverage=True", "hold.deep.var"),
    ])
    def test_e_n1_coverage_row_back_on_the_row_failure_red(self, world, old, new, key):
        prices, _ = world
        prices["0056.TW"] = _ohlcv()
        m = _mutant(PH, (old, new))
        built = _by_key(_three(m, _station(m, (_OK_A, _ERR))))[key]
        assert built[0].state == UI_FAILED and _COVER in _labels(built)

    @pytest.mark.parametrize("old,new,label", [
        ("and _lots < _held and not _cash_skipped:", "and _lots < _held:", _COVER),
        ("if _degraded and not _cash_skipped:", "if _degraded:", _CASH_PART),
    ])
    def test_e_n1_cash_rows_back_on_the_row_failure_red(self, old, new, label):
        m = _mutant(PH, (old, new))
        built = m.build_dividend_cash_card(m.DeepReadout(
            requested=True, submitted=True, bound=True, holdings_n=3, has_station_rows=True,
            cash=_cash_res(), failed_rows=("00878",)))
        assert built[0].state == UI_FAILED and label in _labels(built)

    def test_e_n1_dropping_it_everywhere_is_caught_by_the_keep_tests(self, world):
        """反向：不看觸發原因、一律不出 → ③④ 既有紅態的「涵蓋範圍」也不見了（必須抓到）。"""
        prices, _ = world
        prices["0056.TW"] = _ohlcv()
        prices["2330.TW"] = ConnectionError("yahoo 429")
        m = _mutant(PH, ("coverage=not _var_skipped", "coverage=False"))
        var = _by_key(_three(m, _station(m, (_OK_A, _OK_B))))["hold.deep.var"]
        assert var[0].state == UI_FAILED and _COVER not in _labels(var)

    # ── N5：QA 的 M4／M6／M13（原樣取自 QA 突變表）──────────────────────────
    def test_e_qa_m4_tw_exception_plus_two_ok_treated_as_failure(self, world):
        prices, _ = world
        prices["0056.TW"] = ConnectionError("yahoo 429")
        prices["0056.TWO"] = _ohlcv()
        m = _mutant(PDS, ("        if _df is None and _l1_failed:", "        if _l1_failed:"))
        res = m.get_portfolio_var([_OK_A], strict=True)
        assert res.fetch_errors, "M4 之下 `.TWO` 抓到的那一檔也被當成失敗 —— N5 第一條必須抓到"

    def test_e_qa_m6_failed_not_forwarded_to_two(self, world):
        prices, _ = world
        prices["0056.TWO"] = ConnectionError("yahoo 429")
        m = _mutant(PDS, ("    _df2 = fetch_etf_price(_alt, period=_VAR_PRICE_PERIOD, **_kw)",
                          "    _df2 = fetch_etf_price(_alt, period=_VAR_PRICE_PERIOD)"))
        res = m.get_portfolio_var([_OK_A], strict=True)
        assert res.fetch_errors == () and res.no_price == ("0056.TW",), (
            "M6 之下 `.TWO` 的例外又被當成「沒有歷史」—— N5 第二條必須抓到")

    def test_e_qa_m13_log_line_removed(self, world, capsys):
        prices, _ = world
        prices["0056.TW"] = ConnectionError("yahoo 429")
        m = _mutant(PDS, ("            print(f\"[portfolio_deep/var] {_tk} 價格抓取失敗（L1 已接住）：\"\n"
                          "                  f\"{'；'.join(_l1_failed)}\")\n", ""))
        capsys.readouterr()
        res = m.get_portfolio_var([_OK_A], strict=True)
        assert res.fetch_errors and "L1 已接住" not in capsys.readouterr().out

    # ── 合併前：紅卡不出「兩套算法對不起來」的突變 ─────────────────────────────
    @pytest.mark.parametrize("old,new,key", [
        ("coverage=not _stress_skipped,\n                            red=_state == UI_FAILED)",
         "coverage=not _stress_skipped,\n                            red=False)", "hold.deep.stress"),
        ("coverage=not _var_skipped,\n                            red=_state == UI_FAILED)",
         "coverage=not _var_skipped,\n                            red=False)", "hold.deep.var"),
    ])
    def test_e_recon_call_site_not_passing_red_is_caught(self, world, unreconciled, old, new, key):
        prices, _ = world
        prices["0056.TW"] = _ohlcv()
        m = _mutant(PH, (old, new))
        built = _by_key(_three(m, _station(m, (_OK_A, _ERR))))[key]
        assert built[0].state == UI_FAILED and _RECON in _labels(built)

    def test_e_recon_guard_removed_is_caught(self, world, unreconciled):
        prices, _ = world
        prices["0056.TW"] = ConnectionError("yahoo 429")
        prices["2330.TW"] = ConnectionError("yahoo 429")
        m = _mutant(PH, _RECON_REVERT)
        var = _by_key(_three(m, _station(m, (_OK_A, _OK_B))))["hold.deep.var"]
        assert var[0].state == UI_FAILED and _RECON in _labels(var)

    def test_e_recon_dropped_everywhere_is_caught_by_the_orange_test(self, world, unreconciled):
        """反向：一律不出 → 橘卡上的理由不見了（必須抓到）。"""
        prices, _ = world
        prices["0056.TW"] = _ohlcv()
        m = _mutant(PH, (_RECON_REVERT[0], "    if False:"))
        var = _by_key(_three(m, _station(m, (_OK_A,))))["hold.deep.var"]
        assert var[0].state == UI_DEGRADED and _RECON not in _labels(var)
