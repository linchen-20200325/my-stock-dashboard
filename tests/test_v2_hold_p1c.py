"""批 P1c：持股頁兩條「失敗被讀成沒結果」—— B6-r4、Q3-r3。

  · **B6-r4**（`hold.position_cap`）：warroom 可用、`macro_state.json` **存在卻讀壞**時，
    `get_macro_state` 靠 warroom 判得出位階（`is_loaded=True`），但「macro_state 曝險上限」
    那條輸入悄悄消失 → 上限格畫出一個**少一條天花板**的區間，無紅、無說明。
    修法（加性）：`get_macro_state(strict=True)` 在這一種情形多帶 `file_error` 鍵；
    `get_allocation(strict=True)` 見到就拋 → L5 既有紅態 `CAP_FAILED_NOW`。
    warroom 可用＋檔**不存在** → 不變；預設 `strict=False` → 一個鍵都不多。
  · **Q3-r3**（`hold.deep.stress`／`hold.deep.dividend_cash`）：`_resolve_yf_ticker` 吞例外回
    `None`、`_yf_tickers` 退回 `.TW` → 上櫃股拿錯後綴查 Beta／配息 → 被讀成「Beta 是估的」
    「貢獻 0 元」。修法（加性）：`_resolve_yf_ticker(failed=)` → `_yf_tickers(failed=)` →
    `get_portfolio_stress(strict=)`（`fetch_errors`）／`get_dividend_cash_flow(strict=)`
    （併進既有 `failed_tickers`）→ 既有紅態 `STRESS_FAILED_NOW`／`CASH_FAILED_NOW`。
    **只有被接住的例外算失敗**；只回空、沒拋例外（真卡 ④）照舊。

每條：(a) 全失敗 → 紅；(b) 部分失敗 → 紅；(c) 真的沒有 → 與修前 byte-identical；
(d) 既有呼叫端（不傳新參數）不變；(e) 突變：拿掉任一條守衛 → (a) 轉回非紅。
**無新文案**：紅卡 now 一律是既有常數。
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import types

import pandas as pd
import pytest

import src.compute.etf.etf_calc as EC
import src.data.etf.etf_fetch as F
import src.services.allocation_service as AL
import src.services.dividend_tax_service as DTS
import src.services.macro_state_locker as MSL
import src.services.portfolio_deep_service as PDS
from shared.ui_state import UI_FAILED, UI_LIVE
from src.ui.views import page_hold as PH

_SUBMITTED = PH.HoldRequest(submitted=True)


def _mutant(mod: types.ModuleType, *pairs: tuple[str, str]) -> types.ModuleType:
    """把 `mod` 原始碼裡每一組 `old` **恰好一處**換成 `new`，載成獨立新模組。"""
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    for old, new in pairs:
        assert src.count(old) == 1, f"突變點不唯一或已不存在：{old!r}"
        src = src.replace(old, new)
    name = f"_mutant_p1c_{mod.__name__.rsplit('.', 1)[-1]}"
    spec = importlib.util.spec_from_loader(name, loader=None)
    m = importlib.util.module_from_spec(spec)
    m.__file__ = mod.__file__
    sys.modules[name] = m
    try:
        exec(compile(src, mod.__file__, "exec"), m.__dict__)
    finally:
        sys.modules.pop(name, None)
    return m


# ══════════════════════════════════════════════════════════════════
# B6-r4 hold.position_cap
# ══════════════════════════════════════════════════════════════════
_WR = {"health_score": 70.0, "effective_regime": "bull"}
_GOOD_STATE = {"market_regime": "多頭", "exposure_limit_pct": 80}
_BAD = ["{bad json", {"market_regime": "系統異常", "exposure_limit_pct": 0}, {"foo": 1}]

#: L3 本批守衛整段中和（＝修前）。
_AL_REVERT = (("    if strict and _ms.get('file_error'):", "    if False:"),)
# D3（DL-f1-s65）起該條件多一個「過期裁決不算讀壞」子句，錨點同步（突變語意不變）。
# 批 Z36（Q-z19）起再多一個「8 項全缺落檔不算讀壞」子句，錨點同步（突變語意不變）。
_MSL_REVERT = (("    if (strict and _wr_ok and not _file_ok and os.path.exists(state_file_path)\n"
                "            and not _file_expired and not _file_no_data):",
                "    if False:"),)


@pytest.fixture
def cap_dir(tmp_path, monkeypatch):
    """CWD → tmp（`macro_state.json` 是相對路徑）；session 換成含 warroom 的 dict。"""
    monkeypatch.chdir(tmp_path)
    _ss: dict = {"warroom_summary": dict(_WR)}
    monkeypatch.setattr(AL, "st", types.SimpleNamespace(session_state=_ss))
    return tmp_path


def _write(path: pathlib.Path, obj) -> None:
    path.write_text(obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False),
                    encoding="utf-8")


def _cap(mod=PH):
    return mod.build_position_cap_card(mod.load_allocation(_SUBMITTED))


class TestB6r4PositionCap:
    @pytest.mark.parametrize("content", _BAD)
    def test_a_warroom_ok_but_file_broken_is_red(self, cap_dir, content):
        _write(cap_dir / "macro_state.json", content)
        _c = _cap()[0]
        assert _c.state == UI_FAILED and _c.note.now == PH.CAP_FAILED_NOW
        assert "macro_state.json" in _c.note.why

    def test_b_partial_regime_still_evaluated_but_file_error_surfaced(self, cap_dir):
        """部分失敗：位階由 warroom 撐住（不拋、is_loaded=True），但 file_error 必須帶出來。"""
        _write(cap_dir / "macro_state.json", "{bad json")
        _s = MSL.get_macro_state(_WR, strict=True)
        assert _s["is_loaded"] is True and _s["regime"] == "bull"
        assert _s["file_error"].startswith("macro_state.json")
        with pytest.raises(RuntimeError, match="macro_state.json"):
            AL.get_allocation(strict=True)

    def test_c_missing_file_is_byte_identical(self, cap_dir):
        assert MSL.get_macro_state(_WR, strict=True) == MSL.get_macro_state(_WR)
        assert "file_error" not in MSL.get_macro_state(_WR, strict=True)
        _now = _cap()
        assert _now[0].state == UI_LIVE
        _pre = _mutant(PH, ("_a = get_allocation(strict=True)", "_a = get_allocation()"))
        assert repr(_now) == repr(_cap(_pre))

    def test_c_valid_file_is_byte_identical(self, cap_dir):
        _write(cap_dir / "macro_state.json", _GOOD_STATE)
        assert MSL.get_macro_state(_WR, strict=True) == MSL.get_macro_state(_WR)
        _now = _cap()
        assert _now[0].state == UI_LIVE
        _pre = _mutant(PH, ("_a = get_allocation(strict=True)", "_a = get_allocation()"))
        assert repr(_now) == repr(_cap(_pre))

    def test_d_default_callers_unchanged(self, cap_dir):
        _write(cap_dir / "macro_state.json", "{bad json")
        _d = MSL.get_macro_state(_WR)
        assert "file_error" not in _d and _d["is_loaded"] is True
        assert "file_error" not in AL.get_macro_regime()
        assert AL.get_allocation().is_loaded is True       # 不拋、照舊

    def test_e_mutant_allocation_guard(self, cap_dir, monkeypatch):
        _write(cap_dir / "macro_state.json", "{bad json")
        _m = _mutant(AL, *_AL_REVERT)
        _m.st = AL.st
        monkeypatch.setattr(AL, "get_allocation", _m.get_allocation)
        assert _cap()[0].state == UI_LIVE, "拿掉 L3 allocation 守衛後應回到修前（靜默 live）"

    def test_e_mutant_locker_flag(self, cap_dir, monkeypatch):
        _write(cap_dir / "macro_state.json", "{bad json")
        _m = _mutant(MSL, *_MSL_REVERT)
        monkeypatch.setattr(MSL, "get_macro_state", _m.get_macro_state)
        assert _cap()[0].state == UI_LIVE, "拿掉 file_error 旗標後應回到修前（靜默 live）"


# ══════════════════════════════════════════════════════════════════
# Q3-r3 hold.deep.stress ／ hold.deep.dividend_cash
# ══════════════════════════════════════════════════════════════════
_OK = {"代號": "2330", "種類": "個股", "held": True, "張數": 1.0, "均價": 500.0,
       "現價": 600.0, "市值": 600.0, "_detail": {}}
_OTC = {"代號": "5314", "種類": "個股", "held": True, "張數": 2.0, "均價": 30.0,
        "現價": 35.0, "市值": 70.0, "_detail": {}}

#: L5 本批改動中和（＝修前：兩支不傳 strict）。
_PH_REVERT = (
    ("_guarded(lambda _r: get_portfolio_stress(_r, strict=True),\n"
     "                                    _rows, \"壓力測試\")",
     "_guarded(get_portfolio_stress, _rows, \"壓力測試\")"),
    ("_guarded(lambda _r: get_dividend_cash_flow(_r, strict=True),\n"
     "                                _rows, \"配息現金流\")",
     "_guarded(get_dividend_cash_flow, _rows, \"配息現金流\")"),
)


def _ohlcv(n: int = 60) -> pd.DataFrame:
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=n)
    close = [100.0 + ((i * 7) % 11) - 5 for i in range(n)]
    return pd.DataFrame({"Open": close, "High": [c + 1 for c in close],
                         "Low": [c - 1 for c in close], "Close": close,
                         "Volume": [1000] * n}, index=idx)


def _div_recent() -> pd.Series:
    return pd.Series([1.5], index=[pd.Timestamp.today().normalize() - pd.Timedelta(days=30)])


class _FakeYF:
    """真的 L1 `_fetch_etf_price_max` 打的 `yf.Ticker(t).history()`：
    DataFrame → 有價；Exception → 拋（L1 接住、回空＋旗標）；沒這個鍵 → 回空（沒拋）。"""

    def __init__(self, table: dict):
        self.table = table

    def Ticker(self, t):  # noqa: N802
        step = self.table.get(t)

        class _T:
            def history(self, *a, **k):
                if isinstance(step, Exception):
                    raise step
                return pd.DataFrame() if step is None else step.copy()

        return _T()


@pytest.fixture
def world(monkeypatch):
    prices: dict = {"2330.TW": _ohlcv()}
    divs: dict = {"2330.TW": _div_recent()}
    monkeypatch.setattr(F, "yf", _FakeYF(prices))
    monkeypatch.setattr(EC, "fetch_etf_info", lambda t: {})
    monkeypatch.setattr(DTS, "holding_currency", lambda t: "TWD")
    monkeypatch.setattr(DTS, "fetch_etf_dividends",
                        lambda t: divs.get(t, pd.Series(dtype=float)))
    F._fetch_etf_price_max.clear()
    yield prices, divs
    F._fetch_etf_price_max.clear()


def _station(P, rows):
    return P.StationReadout(requested=True, submitted=True, bound=True,
                            holdings_n=len(rows), rows=tuple(rows))


def _two(P, rows):
    dp = P.load_deep(_station(P, rows))
    return P.build_stress_card(dp), P.build_dividend_cash_card(dp)


def _boom(prices):
    prices["5314.TW"] = ConnectionError("boom")
    prices["5314.TWO"] = ConnectionError("boom2")


class TestQ3r3ResolveFailure:
    def test_a_all_failed_is_red(self, world):
        _boom(world[0])
        _s, _c = _two(PH, [_OTC])
        assert _s[0].state == UI_FAILED and _s[0].note.now == PH.STRESS_FAILED_NOW
        assert _c[0].state == UI_FAILED and _c[0].note.now == PH.CASH_FAILED_NOW
        assert "ConnectionError" in _s[0].note.why and "ConnectionError" in _c[0].note.why
        # 不得再被讀成「貢獻 0 元」
        assert not any("貢獻 0 元" in k for k, _v in _c[1])

    def test_b_partial_failed_is_red(self, world):
        _boom(world[0])
        _s, _c = _two(PH, [_OK, _OTC])
        assert _s[0].state == UI_FAILED and _s[0].note.now == PH.STRESS_FAILED_NOW
        assert _c[0].state == UI_FAILED and _c[0].note.now == PH.CASH_FAILED_NOW
        _r = PDS.get_dividend_cash_flow([_OK, _OTC], strict=True)
        assert _r.failed_tickers and "5314" in _r.failed_tickers[0]
        assert not any("5314" in t for t in _r.no_payout_tickers)

    def test_b_other_suffix_resolves_is_not_failure(self, world):
        """`.TW` 拋例外但 `.TWO` 抓到 → 解出來了，不算失敗。"""
        world[0]["5314.TW"] = ConnectionError("boom")
        world[0]["5314.TWO"] = _ohlcv()
        _f: list = []
        assert PDS._resolve_yf_ticker("5314.TW", failed=_f) == "5314.TWO" and _f == []

    def test_c_genuine_empty_is_byte_identical(self, world):
        """只回空、沒拋例外（真卡 ④）→ 與修前 L5 逐位元組相同。"""
        _now = _two(PH, [_OK, _OTC])
        _pre = _two(_mutant(PH, *_PH_REVERT), [_OK, _OTC])
        assert repr(_now) == repr(_pre)
        assert PDS.get_portfolio_stress([_OTC], strict=True).fetch_errors == ()
        assert (PDS.get_dividend_cash_flow([_OTC], strict=True)
                == PDS.get_dividend_cash_flow([_OTC]))

    def test_d_default_callers_unchanged(self, world):
        _boom(world[0])
        assert PDS._resolve_yf_ticker("5314.TW") is None
        _r = PDS.get_dividend_cash_flow([_OTC])
        assert _r.failed_tickers == () and _r.no_payout_tickers        # 修前：讀成 0 元
        _st = PDS.get_portfolio_stress([_OTC])
        assert _st.fetch_errors == () and "fetch_errors" not in repr(_st)
        assert PDS.get_portfolio_stress([_OTC]) == PDS.get_portfolio_stress([_OTC], strict=True)

    def test_e_mutant_l5_without_strict(self, world):
        _boom(world[0])
        _s, _c = _two(_mutant(PH, *_PH_REVERT), [_OTC])
        assert _s[0].state != UI_FAILED and _c[0].state != UI_FAILED

    def test_e_mutant_resolver_swallows(self, world, monkeypatch):
        _boom(world[0])
        _m = _mutant(PDS, ('    if _used is None and _l1:', '    if False:'),
                     ('        if failed is not None:\n'
                      '            failed.append(f"{type(_e).__name__}: {_e}")', '        pass'))
        monkeypatch.setattr(PDS, "_resolve_yf_ticker", _m._resolve_yf_ticker)
        _s, _c = _two(PH, [_OTC])
        assert _s[0].state != UI_FAILED and _c[0].state != UI_FAILED

    def test_e_mutant_stress_card_ignores_fetch_errors(self, world):
        _boom(world[0])
        _m = _mutant(PH, ('        else (getattr(_res, "fetch_errors", ()) or ()))',
                          '        else ())'))
        assert _two(_m, [_OTC])[0][0].state != UI_FAILED
